import re
import pandas as pd
from collections import defaultdict
import argparse
from bokeh.core.property.nullable import Nullable


"""
@Author: EugeneYu
@Data: 2025/4/24
@Desc: 对app的构建产物进行解析，提取使用设备标识符的调用方
"""

keywords = ["MEID", "IMSI", "MAC", "IMEI", "SERIAL", "ICCID", "getDeviceId"]

def extractHookEntries(text):
    lines = text.split('\n')
    hook_entries = []
    current_entry = []
    in_hook_entry = False

    for line in lines:
        line = line.strip()
        if line.startswith('hook:'):
            if current_entry:
                hook_entries.append('\n'.join(current_entry))
                current_entry = []
            in_hook_entry = True
            current_entry.append(line)
        elif in_hook_entry:
            if line:
                current_entry.append(line)
            else:
                if current_entry:
                    hook_entries.append('\n'.join(current_entry))
                    current_entry = []
                in_hook_entry = False

    if current_entry:
        hook_entries.append('\n'.join(current_entry))

    return hook_entries


def processHookEntries(hook_list):
    results = []

    for entry in hook_list:
        lines = entry.split('\n')

        second_line = lines[1]
        method_match = re.search(r'method=([^\s>]+)', second_line)
        if not method_match:
            continue

        nativeMethod = method_match.group(1)


        keyword = isKeyWord(nativeMethod, keywords)
        if keyword == Nullable:
            continue

        class_match = re.search(r'name=([^\s,]+)', second_line)
        clazz = class_match.group(1) if class_match else ""

        third_line = lines[2]
        name_match = re.search(r'name=([^\s,]+)', third_line)
        hookMethod = name_match.group(1) if name_match else ""

        results.append({
            "keyWord": keyword,
            "class: ": clazz,
            "nativeMethod: ": nativeMethod,
            "HookMethod: ": hookMethod
        })
        print(results)

    return results

def isKeyWord(method, keywords):
    for keyword in keywords:
        if keyword.upper() in method.upper():
            return keyword
    return Nullable

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="params")
    parser.add_argument("--input", "-i", default="./report.txt")
    parser.add_argument("--output", "-o", default="./hook_analysis.xlsx")

    args = parser.parse_args()


    with open(args.input, 'r', encoding='utf-8') as file:
        txt = file.read()

    hook_list = extractHookEntries(txt)
    processed_data = processHookEntries(hook_list)

    df = pd.DataFrame(processed_data)
    df.to_excel(args.output, index=False)