# Written by Dylan Kenneth Eliot

"""
if importing the normal way does not work as expected, use the Git_import2 instead.

"""

wget=__import__("requests").get
def Github_import(username, repo, branch, path_to_module):
  global wget
  return eval(repr(wget("https://raw.githubusercontent.com/"+username+"/"+repo+"/"+branch+"/"+path_to_module).text))

class Git_import(): 
  def __init__(self, username, repo, branch, path_to_module):
    self.username, self.repo, self.branch, self.path_to_module=username, repo, branch, path_to_module
    self.__all__=[]
  def __enter__(self):
    global Github_import
    exec(Github_import(username=self.username,repo=self.repo,branch=self.branch, path_to_module=self.path_to_module))
    for a in dir():
      if a.count('self') != 1 and a.count('Github_import') != 1 :
        exec("self.{0}={0}".format(a))
    del self.branch, self.repo, self.path_to_module, self.username
    return self
  def __exit__(self, exc_type, exc_value, exc_traceback):
    del self

def Github_import2(username, repo, branch, path_to_module):
    global wget
    # Ensure branches other than "main" are prefixed with "refs/heads/"
    if branch != "main" and not branch.startswith("refs/heads/"):
        branch = f"refs/heads/{branch}"
    
    # Generate the GitHub raw URL
    url = f"https://raw.githubusercontent.com/{username}/{repo}/{branch}/{path_to_module}"
    
    # Fetch the module content
    response = wget(url)
    if response.status_code == 200:
        return eval(repr(response.text))  # Evaluate and return the module content
    raise ImportError(f"Module not found in branch: {branch}")

class Git_import2():
    def __init__(self, username, repo, branch, path_to_module):
        self.username, self.repo, self.branch, self.path_to_module = username, repo, branch, path_to_module
        self.__all__ = []

    def __enter__(self):
        global Github_import
        exec(Github_import2(username=self.username, repo=self.repo, branch=self.branch, path_to_module=self.path_to_module))
        for a in dir():
            if a.count('self') != 1 and a.count('Github_import') != 1:
                exec(f"self.{a} = {a}")
        del self.branch, self.repo, self.path_to_module, self.username
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        del self


