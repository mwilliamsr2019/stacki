#! /opt/stack/bin/python
# 
# @SI_Copyright@
#                               stacki.com
#                                  v3.2
# 
#      Copyright (c) 2006 - 2016 StackIQ Inc. All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#  
# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#  
# 2. Redistributions in binary form must reproduce the above copyright
# notice unmodified and in its entirety, this list of conditions and the
# following disclaimer in the documentation and/or other materials provided 
# with the distribution.
#  
# 3. All advertising and press materials, printed or electronic, mentioning
# features or use of this software must display the following acknowledgement: 
# 
# 	 "This product includes software developed by StackIQ" 
#  
# 4. Except as permitted for the purposes of acknowledgment in paragraph 3,
# neither the name or logo of this software nor the names of its
# authors may be used to endorse or promote products derived from this
# software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY STACKIQ AND CONTRIBUTORS ``AS IS''
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL STACKIQ OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# @SI_Copyright@
#
# @Copyright@
#  				Rocks(r)
#  		         www.rocksclusters.org
#  		         version 5.4 (Maverick)
#  
# Copyright (c) 2000 - 2010 The Regents of the University of California.
# All rights reserved.	
#  
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#  
# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#  
# 2. Redistributions in binary form must reproduce the above copyright
# notice unmodified and in its entirety, this list of conditions and the
# following disclaimer in the documentation and/or other materials provided 
# with the distribution.
#  
# 3. All advertising and press materials, printed or electronic, mentioning
# features or use of this software must display the following acknowledgement: 
#  
# 	"This product includes software developed by the Rocks(r)
# 	Cluster Group at the San Diego Supercomputer Center at the
# 	University of California, San Diego and its contributors."
# 
# 4. Except as permitted for the purposes of acknowledgment in paragraph 3,
# neither the name or logo of this software nor the names of its
# authors may be used to endorse or promote products derived from this
# software without specific prior written permission.  The name of the
# software includes the following terms, and any derivatives thereof:
# "Rocks", "Rocks Clusters", and "Avalanche Installer".  For licensing of 
# the associated name, interested parties should contact Technology 
# Transfer & Intellectual Property Services, University of California, 
# San Diego, 9500 Gilman Drive, Mail Code 0910, La Jolla, CA 92093-0910, 
# Ph: (858) 534-5815, FAX: (858) 534-7345, E-MAIL:invent@ucsd.edu
#  
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS''
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# @Copyright@

import string
import types
import sys
import os
import time
import xml.dom.NodeFilter
import xml.dom.ext.reader.Sax2
import stack.js
import stack.cond
	
		

class NodeFilter(xml.dom.NodeFilter.NodeFilter):

	def __init__(self, attrs):
		self.attrs = attrs

	def isCorrectCond(self, node):

		attr = node.attributes.getNamedItem((None, 'arch'))
		if attr:
			arch = attr.value
		else:
			arch = None

		attr = node.attributes.getNamedItem((None, 'os'))
		if attr:
			os = attr.value
			if os == 'linux':
				os = 'redhat'
		else:
			os = None

		attr = node.attributes.getNamedItem((None, 'release'))
		if attr:
			release = attr.value
		else:
			release = None

		attr = node.attributes.getNamedItem((None, 'cond'))
		if attr:
			cond = attr.value
		else:
			cond = None

		expr = stack.cond.CreateCondExpr(arch, os, release, cond)
		return stack.cond.EvalCondExpr(expr, self.attrs)



class ProfileSnippet:
        
        def __init__(self, text, source):
                self.source	= source
                self.text	= text

        def getText(self):
                return self.text

        def getSource(self):
                return self.source

                

class ProfileSection:

        def __init__(self):
                self.snippets = []

        def append(self, text, source=None):
                self.snippets.append(ProfileSnippet(text, source))

        def generate(self, cdata=True):
                prev = None
                open = False
                list = []

                if cdata:
                        cdataStart = '<![CDATA['
                        cdataEnd   = ']]>'
                else:
                        cdataStart = ''
                        cdataEnd   = ''

                for snippet in self.snippets:
                        source = snippet.getSource()
                        text   = snippet.getText()

                        if not source:
                                source = 'internal'

                        if source != prev:
                                if open:
                                        list.append('\t\t%s</subsection>' % cdataEnd)
                                list.append('\t\t<subsection source="%s">%s' % 
                                            (source, cdataStart))
                                open = True
                        list.append(snippet.getText())
                        prev = source
                if open:
	                list.append('\t\t%s</subsection>' % cdataEnd)
                return list

		
class Generator:
	"""Base class for various DOM based kickstart graph generators.
	The input to all Generators is assumed to be the XML output of KPP."""
	
	def __init__(self):
		self.attrs		= {}
                self.arch		= None
		self.rcsFiles		= {}
                self.nodeFilesDict	= {}
                self.nodeFilesList	= []
                self.debugSection	= ProfileSection()
                self.mainSection	= ProfileSection()

	def setArch(self, arch):
		self.arch = arch
		
	def getArch(self):
		return self.arch
	
	def setOS(self, osname):
		self.os = osname
		
	def getOS(self):
		return self.os

	def rcsBegin(self, file, owner, perms):
		"""
		If the is the first time we've seen a file ci/co it.  Otherwise
		just track the ownership and perms from the <file> tag .
		"""
		
		rcsdir	= os.path.join(os.path.dirname(file), 'RCS')
		rcsfile = '%s,v' % os.path.join(rcsdir, os.path.basename(file))
		l	= []

		l.append('')

		if file not in self.rcsFiles:
			l.append('if [ ! -f %s ]; then' % rcsfile)
			l.append('\tif [ ! -f %s ]; then' % file)
			l.append('\t\ttouch %s;' % file)
			l.append('\tfi')
			l.append('\tif [ ! -d %s ]; then' % rcsdir)
			l.append('\t\tmkdir -m 700 %s' % rcsdir)
			l.append('\t\tchown 0:0 %s' % rcsdir)
		 	l.append('\tfi;')
			l.append('\techo "original" | /opt/stack/bin/ci -q %s;' %
			 	file)
                        l.append('\t/opt/stack/bin/rcs -noriginal: %s;' % file)
			l.append('\t/opt/stack/bin/co -q -f -l %s;' % file)
			l.append('fi')

		# If this is a subsequent file tag and the optional PERMS
		# or OWNER attributes are missing, use the previous value(s).
		
		if self.rcsFiles.has_key(file):
			(orig_owner, orig_perms) = self.rcsFiles[file]
			if not perms:
				perms = orig_perms
			if not owner:
				owner = orig_owner

		self.rcsFiles[file] = (owner, perms)
		
		if owner:
			l.append('chown %s %s' % (owner, file))
			l.append('chown %s %s' % (owner, rcsfile))

		if perms:
			l.append('chmod %s %s' % (perms, file))

		l.append('')

		return string.join(l, '\n')

	def rcsEnd(self, file, owner, perms):
		"""
		Run the final ci/co of a <file>.  The ownership of both the
		file and rcs file are changed to match the last requested
		owner in the file tag.  The perms of the file (not the file
		file) are also modified.

		The file is checked out locked, which is why we don't modify
		the perms of the RCS file itself.
		"""
		rcsdir	= os.path.join(os.path.dirname(file), 'RCS')
		rcsfile = '%s,v' % os.path.join(rcsdir, os.path.basename(file))
		l	= []

		l.append('')
		l.append('if [ -f %s ]; then' % file)
		l.append('\techo "stack" | /opt/stack/bin/ci -q %s;' % file)
		l.append('\t/opt/stack/bin/rcs -Nstack: %s;' % file)
		l.append('\t/opt/stack/bin/co -q -f -l %s;' % file)
		l.append('fi')

		if owner:
			l.append('chown %s %s' % (owner, file))
			l.append('chown %s %s' % (owner, rcsfile))

		if perms:
			l.append('chmod %s %s' % (perms, file))

		return string.join(l, '\n')

	
        def getAttr(self, node, attr):
		a = node.attributes.getNamedItem((None, attr))
                if a:
                        return a.value
                else:
                        return ''
                
	
	def order(self, node):
		"""
		Stores the order of traversal of the nodes
		Useful for debugging.
		"""
                nodefile = self.getAttr(node, 'file')

                if nodefile and nodefile not in self.nodeFilesDict:
                        self.nodeFilesDict[nodefile] = True
                        self.nodeFilesList.append(nodefile)
		
	def handle_mainChild(self, node):
		attr = node.attributes
		if attr.getNamedItem((None, 'file')):
			nodefile = attr.getNamedItem((None, 'file')).value
                else:
                        nodefile = None
                try:
			fn = eval('self.handle_main_%s' % node.nodeName)
                except AttributeError:
                        fn = None
                if fn:
                        text = fn(node)
                else:
                        text = '%s %s' % (node.nodeName, self.getChildText(node))
                self.mainSection.append(text, nodefile)



		
	def parseFile(self, node):
		attr = node.attributes

		if attr.getNamedItem((None, 'os')):
			OS = attr.getNamedItem((None, 'os')).value
			if OS != self.getOS():
				return ''

		if attr.getNamedItem((None, 'name')):
			fileName = attr.getNamedItem((None, 'name')).value
		else:
			fileName = ''

		if attr.getNamedItem((None, 'mode')):
			fileMode = attr.getNamedItem((None, 'mode')).value
		else:
			fileMode = 'create'

		if attr.getNamedItem((None, 'owner')):
			fileOwner = attr.getNamedItem((None, 'owner')).value
		else:
			fileOwner = ''

		if attr.getNamedItem((None, 'perms')):
			filePerms = attr.getNamedItem((None, 'perms')).value
		else:
			filePerms = ''

		if attr.getNamedItem((None, 'vars')):
			fileQuoting = attr.getNamedItem((None, 'vars')).value
		else:
			fileQuoting = 'literal'

		if attr.getNamedItem((None, 'expr')):
			fileCommand = attr.getNamedItem((None, 'expr')).value
		else:
			fileCommand = None

		# Have the ability to turn off/on RCS checkins
		if attr.getNamedItem((None, 'rcs')):
			t = attr.getNamedItem((None, 'rcs')).value.lower()
			if t == 'false' or t == 'off':
				rcs = False
		else:
			rcs = True

		fileText = self.getChildText(node)

		if fileName:
                        p, f = os.path.split(fileName)
                        s    = 'if [ ! -e %s ]; then mkdir -p %s; fi\n' % (p, p)

			if rcs:
				s += self.rcsBegin(fileName, fileOwner, filePerms)

			if fileMode == 'append':
				gt = '>>'
			else:
				gt = '>'

			if fileCommand:
				s += '%s %s %s\n' % (fileCommand, gt, fileName)
			if not fileText:
				s += 'touch %s\n' % fileName
			else:
				if fileQuoting == 'expanded':
					eof = "EOF"
				else:
					eof = "'EOF'"

				s += "cat %s %s << %s" % (gt, fileName, eof)
				if fileText[0] != '\n':
					s += '\n'
				s += fileText
				if fileText[-1] != '\n':
					s += '\n'
				s += 'EOF\n'

			# If RCS is disabled, we still need to have support
			# for changing permissions, and owners.
			if not rcs:
				if fileOwner:
					s += 'chown %s %s\n' % (fileOwner, fileName)
				if filePerms:
					s += 'chmod %s %s\n' % (filePerms, fileName)
		return s
	
	# <*>
	#	<*> - tags that can go inside any other tags
	# </*>

	def getChildText(self, node):
		text = ''
		for child in node.childNodes:
			if child.nodeType == child.TEXT_NODE:
				text += child.nodeValue
			elif child.nodeType == child.ELEMENT_NODE:
                                try:
                                        fn = eval('self.handle_child_%s' % child.nodeName)
                                except AttributeError:
                                        fn = None
                                if fn:
                                        text += fn(child)
		return text

	
	# <*>
	#	<file>
	# </*>
	
	def handle_child_file(self, node):
		return self.parseFile(node)

	##
	## Generator Section
	##
			
	def generate(self, section, annotation=False):
		"""Dump the requested section of the kickstart file.  If none 
		exists do nothing."""
		list = []
		try:
			f = getattr(self, "generate_%s" % section)
		except AttributeError:
			f = None
		if f:
			list += f()

		return list

	def generate_order(self):
                return self.nodeFilesList

	def generate_debug(self):
                return self.debugSection.generate()


class MainNodeFilter(NodeFilter):

	def acceptNode(self, node):
	
		if node.nodeName in [ 'profile', 'main' ]:
			return self.FILTER_ACCEPT

                if not (node.parentNode and node.parentNode.nodeName == 'main'):
			return self.FILTER_SKIP

		if not self.isCorrectCond(node):
			return self.FILTER_SKIP

		return self.FILTER_ACCEPT


class OtherNodeFilter(NodeFilter):

	def acceptNode(self, node):

		if node.nodeName == 'profile':
			return self.FILTER_ACCEPT

                if node.nodeName in [ '#document', 'main' ]:
                        return self.FILTER_SKIP
			
		if not self.isCorrectCond(node):
			return self.FILTER_SKIP

		return self.FILTER_ACCEPT


class Generator_redhat(Generator):

	def __init__(self):
		Generator.__init__(self)
                self.preSection			= ProfileSection()
                self.postSection		= ProfileSection()
                self.bootSection		= {}
                self.bootSection['pre']		= ProfileSection()
                self.bootSection['post']	= ProfileSection()
                self.packages			= {}
		self.log			= '/var/log/stack-install.log'

                # We could set these elsewhere but this is the current
                # definition of the RedHat Generator.
                #
                # We used to do i386 (not anymore)

                self.setOS('redhat')
		self.setArch('x86_64')

	
	##
	## Parsing Section
	##

	def parse(self, xml_string):
		import cStringIO
		xml_buf = cStringIO.StringIO(xml_string)
		doc = xml.dom.ext.reader.Sax2.FromXmlStream(xml_buf)
		filter = MainNodeFilter(self.attrs)
		iter = doc.createTreeWalker(doc, filter.SHOW_ELEMENT,
			filter, 0)
		node = iter.nextNode()
		
		while node:
			if node.nodeName == 'profile':
				self.handle_profile(node)
			elif node.nodeName == 'main':
				child = iter.firstChild()
				while child:
					self.handle_mainChild(child)
					child = iter.nextSibling()

			node = iter.nextNode()
			
		filter = OtherNodeFilter(self.attrs)
		iter = doc.createTreeWalker(doc, filter.SHOW_ELEMENT,
			filter, 0)
		node = iter.nextNode()
		while node:
			if node.nodeName != 'profile':
				self.order(node)
                                try:
                                        fn = eval('self.handle_%s' % node.nodeName)
                                except AttributeError:
                                        fn = None
                                if fn:
                                        fn(node)
			node = iter.nextNode()


	# <profile>
	
	def handle_profile(self, node):
		# pull out the attr to handle generic conditionals
		# this replaces the old arch/os logic but still
		# supports the old syntax

		if node.attributes:
			attrs = node.attributes.getNamedItem((None, 'attrs'))
			if attrs:
				dict = eval(attrs.value)
				for (k,v) in dict.items():
					self.attrs[k] = v

	# <main>
	#	<clearpart>
	# </main>
	
	def handle_main_clearpart(self, node):
		attr = node.attributes

		if attr.getNamedItem((None, 'partition')):
			arg = attr.getNamedItem((None, 'partition')).value
		else:
			arg = ''

		#
		# the web form sets the environment variable 'partition'
		# (although, we may find that it makes sense for other
		# sources to set it too).
		#
		try:
			os_arg = os.environ['partition']
		except:
			os_arg = ''

		if (arg == '') or (os_arg == '') or (arg == os_arg):
                        return 'clearpart %s' % self.getChildText(node)


	
	# <main>
	#	<lilo>
	# </main>
	
	def handle_main_lilo(self, node):
		return 'bootloader %s' % self.getChildText(node).strip()


	# <main>
	#	<langsupport>
	# </main>

	def handle_main_langsupport(self, node):
		return 'langsupport --default=%s' % self.getChildText(node).strip()


	# <debug>
	
	def handle_debug(self, node):
                self.debugSection.append(self.getChildText(node), 
                                         self.getAttr(node, 'file'))

	
	# <package>

	def handle_package(self, node):
                nodefile = self.getAttr(node, 'file')
		rpm      = self.getChildText(node).strip()
                type     = self.getAttr(node, 'type')

                if self.getAttr(node, 'disable'):
                        enabled = False
                else:
                        enabled = True

                if type == 'meta':
                        rpm = '@%s' % rpm

                # Once a package is disabled it stays disabled, so
                # only update the dictionary if the package doesn't
                # exist or is currently enabled.

                if rpm in self.packages:
                        (e, n) = self.packages[rpm]
                        if e:
                                self.packages[rpm] = (enabled, nodefile)
                else:
                        self.packages[rpm] = (enabled, nodefile)


	# <pre>
	
	def handle_pre(self, node):
                nodefile	= self.getAttr(node, 'file')
                interpreter	= self.getAttr(node, 'interpreter')
                arg		= self.getAttr(node, 'arg')

                s = '%pre'
                if interpreter:
                        s += ' --interpreter %s' % interpreter
                s += ' --log=%s %s' % (self.log, arg)
                s += '\n%s' % self.getChildText(node)
                s += '%end'
			
                self.preSection.append(s, nodefile)


	# <post>
	
	def handle_post(self, node):
                nodefile	= self.getAttr(node, 'file')
                interpreter	= self.getAttr(node, 'interpreter')
                arg		= self.getAttr(node, 'arg')

                s = '%post'
                if interpreter:
                        s += ' --interpreter %s' % interpreter
                if arg and '--nochroot' in arg:
                        s += ' --log=/mnt/sysimage%s %s' % (self.log, arg)
                else:
                        s += ' --log=%s %s' % (self.log, arg)
                s += '\n%s' % self.getChildText(node)
                s += '%end'
			
                self.postSection.append(s, nodefile)


		
	# <boot>
	
	def handle_boot(self, node):
                nodefile	= self.getAttr(node, 'file')
                order		= self.getAttr(node, 'order')
                
                if not order:
                        order	= 'pre'

                s = '%%post --log=%s\n' % self.log
                s += "cat >> /etc/sysconfig/stack-%s << '__EOF__'\n" % order
		s += '%s' % self.getChildText(node)
                s += '__EOF__\n'
                s += '%end'

                self.bootSection[order].append(s, nodefile)


	def generate_main(self):
                return self.mainSection.generate()

	def generate_packages(self):

                section = ProfileSection()
                dict	= {}

                for (rpm, (enabled, nodefile)) in self.packages.items():
                        if not dict.has_key(nodefile):
                                dict[nodefile] = []
                        if not enabled:
                                rpm = '-%s' % rpm
                        dict[nodefile].append(rpm)
                
                for (nodefile, rpms) in dict.items():
                        rpms.sort()
                        for rpm in rpms:
                                section.append(rpm, nodefile)
                        
                list = []
		list.append('%packages --ignoremissing')
                for line in section.generate(cdata=False):
                        list.append(line)
		list.append('%end')
		return list


	def generate_pre(self):
                return self.preSection.generate()

	def generate_post(self):
                return self.postSection.generate()

	def generate_boot(self):
                section = ProfileSection()

		# check in/out all modified files

                s = '%%post --log=%s\n' % self.log
                s += "cat >> /etc/sysconfig/stack-pre << '__EOF__'\n"
		for (file, (owner, perms)) in self.rcsFiles.items():
			s += '%s' % self.rcsEnd(file, owner, perms)
                s += '\n__EOF__\n'
                s += '%end'
		section.append(s)

		list = []

		# Boot PRE

                for line in section.generate():
                        list.append(line)
                for line in self.bootSection['pre'].generate():
                        list.append(line)


		# Boot POST
		
                for line in self.bootSection['post'].generate():
                        list.append(line)

		
		return list

