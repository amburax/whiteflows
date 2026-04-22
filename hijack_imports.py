import re
import os

def hijack_content(content):
    # Rule 1: from pydantic... -> from wf_pydantic...
    content = re.sub(r'(?<=from\s)pydantic(?=[\s\.]|$)', 'wf_pydantic', content)
    # Rule 2: import pydantic -> import wf_pydantic as pydantic
    content = re.sub(r'(?<=import\s)pydantic(?=[\s\.]|$)', 'wf_pydantic as pydantic', content)
    
    content = re.sub(r'(?<=from\s)fastapi(?=[\s\.]|$)', 'wf_fastapi', content)
    content = re.sub(r'(?<=import\s)fastapi(?=[\s\.]|$)', 'wf_fastapi as fastapi', content)
    
    content = re.sub(r'(?<=from\s)starlette(?=[\s\.]|$)', 'wf_starlette', content)
    content = re.sub(r'(?<=import\s)starlette(?=[\s\.]|$)', 'wf_starlette as starlette', content)
    return content

def hijack_namespaces(target_path):
    if os.path.isfile(target_path):
        if target_path.endswith('.py'):
            with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            new_content = hijack_content(content)
            if new_content != content:
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
    elif os.path.isdir(target_path):
        for root, dirs, files in os.walk(target_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    new_content = hijack_content(content)
                    if new_content != content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)

# Run it on api.py and recursively on the libs directory
hijack_namespaces('api.py')
hijack_namespaces('libs')
print("Successfully hijacked namespaces in api.py and libs folder")
