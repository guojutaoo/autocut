import re
text = '在权力的牌桌上，最稳固的位置往往最先坍塌。'
print(re.findall(r'[^,.，。！？；;]+[,.，。！？；;]?', text))
