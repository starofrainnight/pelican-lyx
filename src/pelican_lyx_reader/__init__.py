# -*- coding: utf-8 -*-

import re
import subprocess
import os
import xml.etree.ElementTree as etree
import tempfile
import io
import six
import sys
from six.moves import html_parser
from pelican import signals
from pelican.readers import BaseReader
from pelican.utils import pelican_open
from bs4 import BeautifulSoup

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

def fix_html_element(soup, element):
    # Parse the header line
    matched = re.match(r"h(\d+)", element.name)
    if matched:
        # Wrap header lines into a section div
        new_tag = soup.new_tag("div", class_="section")

        element.attrs = {} # Clear all attributes
        element.wrap(new_tag)
        element = new_tag
        return element

    # Replace tag name of text area to "p"
    if ((element.name == "div")
        and (element.get("class") is not None)
        and (element.get("class")[0] == "standard")):
        element.name = "p"
        element.attrs = {} # Clear all attributes
        return element

    return element

def fix_lyx_xhtml(content):
    soup = BeautifulSoup(content, "html.parser")
    e_body = soup.find("body")
    if e_body is None:
        return str(e_body)

    # Removed title and author lines
    try:
        e_body.find("h1", attrs={"class":"title"}).decompose()
        e_body.find("div", attrs={"class":"author"}).decompose()
    except AttributeError:
        # Not a valid lyx file
        return str(e_body)

    section_stack = []
    div_id = 0

    element = e_body.findChild()
    while element is not None:
        matched = re.match(r"h(\d+)", element.name)

        if matched is not None:
            matched = re.match(r"h(\d+)", element.name)
            section_level = int(matched.group(1))

            element = fix_html_element(soup, element)

            # First backup next element, because we will change the element
            # variant later.
            next_element = element.find_next_sibling()

            # Find the level we should place into
            while len(section_stack) > 0:
                last_section = section_stack[len(section_stack) - 1]
                last_section_name = last_section.find(re.compile(r"h\d+")).name
                last_section_level = int(re.match(r"h(\d+)", last_section_name).group(1))

                if section_level >= last_section_level:
                    # Remove the last element of section_stack
                    del section_stack[len(section_stack) - 1]
                else:
                    last_section.append(element)
                    break

            section_stack.append(element)

            element = next_element
        else:
            next_element = element.find_next_sibling()

            last_section = section_stack[len(section_stack) - 1]
            last_section.append(fix_html_element(soup, element))

            element = next_element

    return str(e_body)

class LyxReader(BaseReader):
    enabled = True
    file_extensions = ['lyx']

    def read(self, filename):

        with io.open(filename, "r", encoding="utf-8") as lyx_file:
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
        if six.PY2:
            command = command.encode("utf-8")
        os.system(command)

        html_content = ""
        with io.open(html_file_path, "r", encoding="utf-8") as html_file:
            html_content = html_file.read()
            html_content = fix_lyx_xhtml(html_content)

        if six.PY2:
            html_content = html_content.decode('utf-8')

        return html_content, metadata

def add_reader(readers):
    for ext in LyxReader.file_extensions:
        readers.reader_classes[ext] = LyxReader

def register():
    signals.readers_init.connect(add_reader)
