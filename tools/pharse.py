import re

def get_document(job_json):
    # 電話號碼
    phone_str = ",".join(job_json['contact']['phone']) if job_json['contact']['phone'] else "無"

    # hr單位
    hr = job_json['contact']['hrName']
    email = job_json['contact']['email']

    contact_str = f'''
        {hr}
        email:{email}
        電話:{phone_str}
    '''
    
    role_str = ', '.join([r['description'] for r in job_json['condition']['acceptRole']['role']]) # 應徵身分
    major_str = ", ".join(job_json['condition']['major']) # 相關科系 
    work_exp = job_json['condition']['workExp'] # 工作經驗
    edu_str = job_json['condition']['edu'] # 教育程度
    # 語言能力
    lang_list = []
    for l in job_json['condition']['language']:
        lang_str = f"{l['language']}(聽力:{l['ability']['listening']},口說:{l['ability']['speaking']},閱讀:{l['ability']['reading']},寫:{l['ability']['writing']})"
        lang_list.append(lang_str)
    language_str = ", ".join(lang_list)

    specialty_str = ", ".join([s['description'] for s in job_json['condition']['specialty']])# 專業與技能
    skill_str = ", ".join([s['description'] for s in job_json['condition']['skill']])
    # 證照+駕照
    certs = [c['name'] for c in job_json['condition']['certificate']]
    license = job_json['condition']['driverLicense']
    cert_str = ", ".join(certs + license)
    # 其他條件
    other = job_json['condition']['other']

    hire_require = f'''
        歡迎所有求職者 與 {role_str}
        科系要求: {major_str}
        工作經驗: {work_exp}
        教育程度: {edu_str}

        語言要求:{language_str}
        擅長工具:{specialty_str}
        工作技能:{skill_str}
        加分證照:{cert_str}
        其他:{other}
    '''
    
    # 福利標籤
    welfare_tag_str = ", ".join(job_json['welfare']['tag'])
    legal_tag_str = ", ".join(job_json['welfare']['legalTag'])
    welfare_str = job_json['welfare']['welfare'] + welfare_tag_str + ", " + legal_tag_str
    
    # 工作細節
    jobDescription = job_json['jobDetail']['jobDescription']
    jobCategory = ','.join([j['description'] for j in job_json['jobDetail']['jobCategory']])
    manageResp = job_json['jobDetail']['manageResp']
    businessTrip = job_json['jobDetail']['businessTrip']

    # 工作時間資訊
    work_shift = f"{','.join(job_json['jobDetail']['workPeriod']['shifts'].keys())} , {job_json['jobDetail']['workPeriod']['note']}" if job_json['jobDetail']['workPeriod'] else ''
    workPeriod = f'''
        工作排班資訊:
        {work_shift}
        休假制度: {job_json['jobDetail']['vacationPolicy']}
        可上班日:{job_json['jobDetail']['startWorkingDay']}
        需不需要出差:{businessTrip}
    '''

    # 薪水
    match job_json['jobDetail']['salaryType']:
        case 50: # 月薪
            salary_str = f"薪水:月薪範圍{job_json['jobDetail']['salaryMin']}-{job_json['jobDetail']['salaryMax']}"
        case 60 | 10 | 30: # 年薪&待遇面議
            salary_str = f"薪水:{job_json['jobDetail']['salary']}"

    job_detail = f'''\
        {jobDescription}

        {jobCategory}
        {manageResp}
        {workPeriod}

        {salary_str}
    '''
    
    # 公司資訊
    jobName = job_json['header']['jobName']
    custName = job_json['header']['custName']
    industry = job_json['industry']
    employees = job_json['employees']

    # 公司地址
    address = job_json['jobDetail']['addressRegion'] + job_json['jobDetail']['addressDetail'] + " " + job_json['jobDetail']['industryArea']

    corp_detail = f'''
公司名稱:{custName}
職務名稱:{jobName}
產業類別:{industry}
公司員工數:{employees}

公司地址:{address}
    '''
    
    document = f'''
        # {custName} - {jobName} 
        ## 公司資訊
        {corp_detail}

        ## 職務細節
        {job_detail}

        ## 公司福利
        {welfare_str}

        ## 徵才條件
        {hire_require}

        ## HR單位 聯絡資訊
        {contact_str}
    '''
    
    return document

def get_metadata(job_json):
    jobType_dict = {0:'兼職',1:'全職',2:'兼職'}
    salaryType_dict = {50:'月薪', 60:'年薪', 10:'待遇面議(40000以上)', 30:'時薪'}
    remoteWork_dict = {1:'完全遠端',2:'部分遠端'}
    meta_data = {
        "jobName": job_json['header']['jobName'],
        "appearDate": job_json['header']['appearDate'],
        "custName": job_json['header']['custName'],
        "custUrl": job_json['header']['custUrl'],
        "analysisUrl": job_json['header']['analysisUrl'],
        "hrBehaviorPR": float(job_json['header']['hrBehaviorPR']),
        "hrName": job_json['contact']['hrName'],
        "hrEmail": job_json['contact']['email'],
        "salaryMin": int(job_json['jobDetail']['salaryMin']),
        "salaryMax": int(job_json['jobDetail']['salaryMax']),
        "salaryType": salaryType_dict[int(job_json['jobDetail']['salaryType'])],
        "jobType": jobType_dict.get(int(job_json['jobDetail']['jobType']),'其他'),
        "address": job_json['jobDetail']['addressRegion'] + job_json['jobDetail']['addressDetail'] + " " + job_json['jobDetail']['industryArea'],
        "industry": job_json['industry'],
        "remoteWork": remoteWork_dict[job_json['jobDetail']['remoteWork']['type']] if job_json['jobDetail']['remoteWork'] else '無',
        "needEmp": job_json['jobDetail']['needEmp'],
        "lastProcessedResumeAtTime": int(job_json['interactionRecord']['lastProcessedResumeAtTime']) if job_json['interactionRecord']['lastProcessedResumeAtTime'] else 0,
        "lastCustReplyTimestamp": int(job_json['interactionRecord']['lastCustReplyTimestamp']) if job_json['interactionRecord']['lastCustReplyTimestamp'] else 0
    }

    return meta_data

def create_chunks(job_id, full_document, base_metadata):
    
    # 2. 準備用來戴帽子的全局變數
    cust_name = base_metadata['custName']
    job_name = base_metadata['jobName']
    
    # 3. 用正規表達式 (Regex) 按 "## " 把文章切開
    # 這邊會切出包含標題和內容的 list
    raw_sections = re.split(r'\n## ', full_document)
    print(len(raw_sections))
    
    chunks_for_chroma = []
    
    for idx,section in enumerate(raw_sections):
        # 去除掉可能多餘的空白
        section = section.strip()
        if not section or section.startswith('#'):
            # 跳過最前面的 "# 允和科技股份有限公司 - Unity資深研發工程師" 這個大標題
            continue
            
        # 把標題跟內容分開 (例如 "公司資訊\n公司名稱:...")
        lines = section.split('\n', 1)
        if len(lines) < 2:
            continue
            
        section_title = lines[0].strip()
        section_content = lines[1].strip()
        
        # 4. 戴帽子！組合全局資訊
        enriched_text = f"【{cust_name} - {job_name}】的{section_title}：\n{section_content}"
        
        # 5. 準備這一個 chunk 的專屬 metadata
        chunk_meta = base_metadata.copy()
        chunk_meta['job_id'] = job_id
        chunk_meta['chunk_type'] = section_title # 順便記一下這塊是福利還是條件
        
        ids = f"{job_id}_{idx+1}"
        
        chunks_for_chroma.append({
            "text": enriched_text,
            "metadata": chunk_meta,
            "ids":ids
        })
        
    return chunks_for_chroma
