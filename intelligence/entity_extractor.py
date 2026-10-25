"""Conservative extraction of common technical entities."""
import re, ipaddress
def extract(text):
    result={'paths':re.findall(r'(?:/[^\s,;]+|\.\.?/[^\s,;]+)',text),'urls':re.findall(r'https?://[^\s]+',text),'ports':[],'ips':[],'hosts':[]}
    for value in re.findall(r'(?<!\d)(\d{1,5})(?!\d)',text):
        n=int(value)
        if 1<=n<=65535 and re.search(r'(?i)(?:port|puerto)\s+'+re.escape(value),text):result['ports'].append(n)
    for value in re.findall(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?',text):
        try:result['ips'].append(str(ipaddress.ip_network(value,strict=False) if '/' in value else ipaddress.ip_address(value)))
        except ValueError:pass
    return result
