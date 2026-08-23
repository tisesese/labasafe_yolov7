import os
import docx

cwd = r'D:\pycharm_projects\yolov7-main\yolov7-main'

# Find by ASCII pattern: +2022080007+ (thesis) vs -2022080007. (short)
for f in os.listdir(cwd):
    if f.endswith('.docx') and '+2022080007+' in f:
        full = os.path.join(cwd, f)
        print(f'Found thesis: {os.path.getsize(full)} bytes')
        print('=' * 80)

        doc = docx.Document(full)

        for i, para in enumerate(doc.paragraphs):
            text = para.text
            if text.strip():
                print(f'[{i}] {text.strip()}')

        # Print table count
        if doc.tables:
            print(f'\n{"=" * 80}')
            print(f'Number of tables: {len(doc.tables)}')
        break
else:
    print("Not found by +2022080007+ pattern, trying all 2022080007 files...")
    for f in os.listdir(cwd):
        if '2022080007' in f and f.endswith('.docx'):
            full = os.path.join(cwd, f)
            print(f'Trying: {os.path.getsize(full)} bytes')
            doc = docx.Document(full)
            first_text = ""
            for p in doc.paragraphs:
                if p.text.strip():
                    first_text = p.text.strip()[:100]
                    break
            print(f'  First text: {first_text}')
            print(f'  Total paragraphs: {len(doc.paragraphs)}')
