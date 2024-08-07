import os
import requests
import urllib.parse
from lxml import etree

BASE_DIR = os.path.join(os.path.dirname(__file__), 'Books')
BASE_URL = ''

parser = etree.HTMLParser()

class Object:
    def __init__(self, name, path):
        self.name = name
        self.path = path
    def __repr__(self):
        return f'<({self.__class__.__name__}) [{self.name}] @ {self.path}'

class FileObj(Object): pass
class FolderObj(Object): pass

def get_results(url):
    response = requests.get(url)
    content = etree.fromstring(response.text, parser)
    results = []
    for each in content.findall('.//a'):
        if (text := each.text) == '../':
            continue
        if not (link := each.attrib.get('href', '')):
            continue
        if text.endswith('/'):
            cls = FolderObj
            text = text[:-1]
        else:
            cls = FileObj
        results.append(cls(text, link))
    return results

def save_file(url, root, result: FileObj):
    response = requests.get(url + result.path, stream=True)
    with open(os.path.join(root, urllib.parse.unquote(result.path)), 'wb') as f:
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                f.write(chunk)

def fetch(url, root):
    if not os.path.exists(root):
        os.mkdir(root)
    for result in get_results(url):
        if type(result) is FolderObj:
            fetch(url + result.path, os.path.join(root, result.name))
        else:
            save_file(url, root, result)

def main():
    fetch(BASE_URL, BASE_DIR)

if __name__ == '__main__':
    main()
