import re
import subprocess
import os
import xml.etree.ElementTree as etree
import tempfile
from pelican import signals
from pelican.readers import BaseReader
from pelican.utils import pelican_open

def lyx_to_xml(content):
    def get_last_of_stack(stack):
        return stack[len(stack) - 1]

    lines = content.splitlines()

    root = etree.Element("lyx")
    tree = etree.ElementTree()
    tree._setroot(root)

    stack = [root]

    line_count = 0
    begin_count = 0
    end_count = 0
    for line in lines:
        line_count += 1

        # Comment lines are ignored
        if line.startswith("#"):
            continue

        # Handle the begin line
        patterns = [
            r".*\\begin_(\w+)\s*(.*)",
            r".*\\(index)(?:\s+(.*))",
        ]
        is_processed = False
        for pattern in patterns:
            matched = re.match(pattern, line)
            if matched is None:
                continue

            element = etree.Element(
                matched.group(1).strip(),
                attrib={'type':matched.group(2)})

            get_last_of_stack(stack).append(element)
            stack.append(element) # Enter a level
            begin_count += 1

            is_processed = True
            break
        if is_processed:
            continue

        # Handle the end line
        pattern = r".*\\end_(\w+).*"
        matched = re.match(pattern, line)
        if matched is not None:
            if get_last_of_stack(stack).tag != matched.group(1):
                raise SyntaxError("Not matched ending tag for : %s at line %s !" % (
                    get_last_of_stack(stack).tag, line_count))

            stack.pop() # Leave a level
            end_count += 1
            continue

        # Handle the element line
        patterns = [
            # Pattern : \xxxx{yyyy}
            r".*\\(\w+)(\{[^\}]*\}.*)",
            # Pattern : \xxxx yyyy
            r".*\\(\w+)\s+([^\}]*.*)",
        ]
        is_processed = False
        for pattern in patterns:
            matched = re.match(pattern, line)
            if matched is None:
                continue

            element = etree.Element(
                matched.group(1).strip(),
                attrib={'value':matched.group(2)})

            get_last_of_stack(stack).append(element)
            is_processed = True
            break
        if is_processed:
            continue

        # Other things are content
        if len(line) > 0:
            text = get_last_of_stack(stack).text
            if text is None:
                text = ''
            else:
                text = text + '\n'

            get_last_of_stack(stack).text = text + line
    return tree

class LyxReader(BaseReader):
    enabled = True
    file_extensions = ['lyx']

    def read(self, filename):
        with open(filename, "r", encoding="utf-8") as lyx_file:
            tree = lyx_to_xml(lyx_file.read())

        element = tree.find("./document/header/preamble")
        founded_list = []
        if element.text is not None:
            founded_list = re.findall(r"%metadata\[([^:]+):([^\]]+)\]", element.text)

        metadata = {}

        # Metadata of 'title' needs to extract from document body
        element = tree.find("./document/body/layout[@type='Title']")
        if (element is not None) and (element.text is not None):
            metadata['title'] = self.process_metadata('title', element.text)

        for kv in founded_list:
            name, value = kv[0].lower(), kv[1].strip()
            metadata[name] = self.process_metadata(name, value)

        with tempfile.NamedTemporaryFile(delete=False) as html_file:
            html_file_path = html_file.name

        command = 'lyx -E xhtml "%s" "%s"' % (html_file_path, os.path.normpath(filename))
        os.system(command)

        html_content = ""
        with open(html_file_path, "r", encoding="utf-8") as html_file:
            html_content = html_file.read()

        return html_content, metadata

def add_reader(readers):
    for ext in LyxReader.file_extensions:
        readers.reader_classes[ext] = LyxReader

def register():
    signals.readers_init.connect(add_reader)
