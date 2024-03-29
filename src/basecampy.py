'''
    BaseCamp API for Python 2.7
    Copyright (C) 2012 Marc Kirchner
    
    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.
'''

import urllib2
import re
import datetime
import xml.etree.ElementTree as ET

# exceptions
class UnknownAttributeType(BaseException):
    pass

# helpers
class RequestWithMethod(urllib2.Request):
    def __init__(self, *args, **kwargs):
        self._method = kwargs.pop('method', None)
        urllib2.Request.__init__(self, *args, **kwargs)

    def get_method(self):
        return self._method if self._method \
            else super(RequestWithMethod, self).get_method()

# here we go...
class Basecamp(object):
    def __init__(self, url, token):
        self.base_url = url
        if self.base_url[-1] == '/':
            self.base_url = self.base_url[:-1]
        # set up basic authentication
        pw_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        # extract the FQDN from the URL
        host = re.match("https?://([^/]+)", url).group(1)
        # we authenticate using the basecamp token and a dummy password
        pw_manager.add_password(None, host, token, 'x')
        authhandler = urllib2.HTTPBasicAuthHandler(pw_manager)
        # create the opener through which all requests will be processed
        self.bc_handle = urllib2.build_opener(authhandler)

    def _request(self, path, method='GET', data=None):
        if isinstance(data, ET._ElementInterface):
            data = ET.tostring(data)
        #print "requesting:  %s/%s" % (self.base_url, path)
        #print "data: %s" % data
        req = RequestWithMethod(url="%s/%s" % (self.base_url, path), method=method, data=data)
        s = self.bc_handle.open(req).read()
        #print "Response: %s" % s
        return s
    
    def get_todo_item(self, item_id):
        path = 'todo_items/%d.xml' % item_id
        response = ET.fromstring(self._request(path))
        return TodoItem(self, response)
    
    def get_todo_list(self, list_id):
        path = 'todo_lists/%u.xml' % list_id
        response = ET.fromstring(self._request(path))
        #print ET.tostring(response)
        return TodoList(self, response)
    
    def get_todo_lists(self, responsible_party=None):
        path = ''
        if responsible_party is None:
            path = 'todo_lists.xml'
        else:
            path = 'todo_lists.xml?responsible_party=%s' % responsible_party
        response = ET.fromstring(self._request(path))
        todo_lists = []
        for i in response.findall("todo-list"):
            tdl = TodoList(self, i)
            todo_lists.append(tdl)
        return todo_lists
    
    def get_person(self, person_id=None):
        path = ''
        if person_id is None:
            path = 'me.xml'
        else:
            path = 'people/%d.xml' % person_id
        response = ET.fromstring(self._request(path))
        return Person(self, response)
    
    def get_people(self):
        path = 'people.xml'
        response = ET.fromstring(self._request(path))
        people = []
        for i in response.findall("person"):
            p = Person(self, i)
            people.append(p)
        return people
    
    def get_companies(self, project_id=None):
        path = ''
        if project_id is None:
            path = 'companies.xml'
        else:
            path = 'projects/%d/companies.xml' % project_id
        response = ET.fromstring(self._request(path))
        companies = []
        for i in response.findall("company"):
            c = Company(self, i)
            companies.append(c)
        return companies
    
    def get_company(self, company_id):
        path = 'companies/%d.xml' % company_id 
        response = ET.fromstring(self._request(path))
        return Company(self, response)
    
    def get_project(self, project_id):
        path = 'projects/%u.xml' % project_id
        response = ET.fromstring(self._request(path))
        return TodoList(self, response)
    
    def get_projects(self):
        path = 'projects.xml'
        response = ET.fromstring(self._request(path))
        #print ET.tostring(response)
        projects = []
        for i in response.findall("project"):
            p = Project(self, i)
            projects.append(p)
        return projects

class BasecampObject(object):
    def __init__(self, basecamp):
        self.bc_handle = basecamp
        
    def fromXml(self, et):
        raise NotImplementedError('fromXML has not been implemented.')
        
    def toXml(self):
        raise NotImplementedError('toXML has not been implemented.')

    def xmlAttr2Attr(self, i):
        if not(i.text is None):
            attr_type = i.get("type", None)
            if attr_type is None:
                # there is no type info for strings
                return i.text
            elif attr_type == "integer":
                return int(i.text)
            elif attr_type == "datetime":
                return datetime.datetime.strptime(
                    i.text, '%Y-%m-%dT%H:%M:%SZ')
            elif attr_type == "date":
                return datetime.datetime.strptime(
                    i.text, '%Y-%m-%d')
            elif attr_type == "boolean":
                return (i.text == "true")
            else:
                raise UnknownAttributeType(attr_type) 
        return None
        
class TodoList(BasecampObject):
    def __init__(self, basecamp, et=None):
        super(TodoList, self).__init__(basecamp)
        self.current = 0
        self.fromXml(et)

    def fromXml(self, et):
        # find the todo-items array
        et_todo_items = et.find("todo-items")
        # iterate over all todo items and generate objects
        self.__dict__['todo_items'] = []
        for i in et_todo_items.findall("todo-item"):
            #print "--> Adding todo-item: %s" % ET.tostring(i)
            t = TodoItem(self.bc_handle, i)
            self.__dict__['todo_items'].append(t)
        # now remove the todo-items array such that we can
        # iterate over the rest
        et.remove(et_todo_items)
        # iterate over the todo-list attributes
        for i in et.iter():
            # the call to iter() iterates over the element itself
            # but you cannot find() the element because find only 
            # works on subelements. Strange API.
            # Consequently we ignore the element itself and just go for the
            # attributes.
            if i.tag == 'todo-list':
                continue
            # make sure the variable names do not contain a dash
            tag = i.tag.replace('-', '_')
            self.__dict__[tag] = self.xmlAttr2Attr(i)
            
    def __str__(self):
        return "[%d] Todo list: %s (%d items)" % (
            self.id, self.name, len(self.todo_items))
        #return str(self.__dict__)

class TodoItem(BasecampObject):
    def __init__(self, basecamp, et=None):
        super(TodoItem, self).__init__(basecamp)
        if not(et is None):
            self.fromXml(et)
        
    def fromXml(self, et):
        # iterate over the todo-item attributes
        #print ET.tostring(et)
        for i in et.iter():
            # [see the comment in TodoList::fromXml!]
            if i.tag == 'todo-item':
                continue
            # make sure the variable names do not contain a dash
            tag = i.tag.replace('-', '_')
            self.__dict__[tag] = self.xmlAttr2Attr(i)
            
    def __repr__(self):
#        s = 'o'
#        if self.completed:
#            s = 'x';
#        return 'TodoItem: %s, %s, %s' % (s, self.content, self.due_at)
        return str(self.__dict__)
    
    def complete(self):
        # complete the item
        path = 'todo_items/%d/complete.xml' % self.id
        self.bc_handle._request(path, 'PUT', '')

    def uncomplete(self):
        # complete the item
        path = 'todo_items/%d/uncomplete.xml' % self.id
        self.bc_handle._request(path, 'PUT', '')

class Person(BasecampObject):
    def __init__(self, basecamp, et=None):
        super(Person, self).__init__(basecamp)
        if not(et is None):
            self.fromXml(et)
        
    def fromXml(self, et):
        for i in et.iter():
            # make sure the variable names do not contain a dash
            tag = i.tag.replace('-', '_')
            self.__dict__[tag] = self.xmlAttr2Attr(i)
            
    def __repr__(self):
        return 'Person: %s, %s (%d)' % (self.last_name, self.first_name, self.id)

class Company(BasecampObject):
    def __init__(self, basecamp, et=None):
        super(Company, self).__init__(basecamp)
        if not(et is None):
            self.fromXml(et)
        
    def fromXml(self, et):
        # iterate over the company attributes
        for i in et.iter():
            # make sure the variable names do not contain a dash
            tag = i.tag.replace('-', '_')
            self.__dict__[tag] = self.xmlAttr2Attr(i)
            
    def __repr__(self):
        return 'Company: %s (%d)' % (self.name, self.id)

    def get_people(self):
        path = 'companies/%d/people.xml' % self.id
        response = ET.fromstring(self.bc_handle._request(path))
        self.people = []
        for i in response.findall("person"):
            p = Person(self.bc_handle, i)
            self.people.append(p)
        return self.people


class Project(BasecampObject):
    def __init__(self, basecamp, et=None):
        super(Project, self).__init__(basecamp)
        if not(et is None):
            self.fromXml(et)
        
    def fromXml(self, et):
        # find, read and remove the company info
        et_company = et.find("company")
        self.__dict__['company'] = Company(et_company)
        et.remove(et_company)
        # iterate over the project attributes
        for i in et.iter():
            # make sure the variable names do not contain a dash
            tag = i.tag.replace('-', '_')
            self.__dict__[tag] = self.xmlAttr2Attr(i)
            
    def __repr__(self):
        return 'Project: %s (%d)' % (self.name, self.id)
    
    def get_companies(self):
        path = 'projects/%d/companies.xml' % self.id
        response = ET.fromstring(self.bc_handle._request(path))
        self.companies = []
        for i in response.findall("company"):
            c = Company(self.bc_handle, i)
            self.companies.append(c)
        return self.companies
    
    def get_people(self):
        path = 'projects/%d/people.xml' % self.id
        response = ET.fromstring(self.bc_handle._request(path))
        self.people = []
        for i in response.findall("person"):
            p = Person(self.bc_handle, i)
            self.people.append(p)
        return self.people
    
    #def get_projects(self):
