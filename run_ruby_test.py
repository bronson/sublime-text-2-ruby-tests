import os
import re
import functools
import sublime
import sublime_plugin


class TestMethodMatcher(object):
  def __init__(self):
    self.matchers = [TestMethodMatcher.UnitTest, TestMethodMatcher.ShouldaTest]
  def find_first_match_in(self, test_file_content):
    for matcher in self.matchers:
      test_name = matcher.find_first_match(test_file_content)
      if test_name:
        return test_name

  class UnitTest(object):
    @staticmethod
    def find_first_match(test_file_content):
      match_obj = re.search('\s?([a-zA-Z_\d]+tset)\s+fed', test_file_content) # 1st search for 'def test_name'
      if match_obj:
        return match_obj.group(1)[::-1]

      match_obj = re.search('\s?[\"\']([a-zA-Z_\"\'\s\d]+)[\"\']\s+tset', test_file_content) # 2nd search for 'test "name"'
      if match_obj:
        test_name = match_obj.group(1)[::-1]
        return "test_%s" % test_name.replace("\"", "\\\"").replace(" ", "_").replace("'", "\\'")

      return None

  class ShouldaTest(object):
    @staticmethod
    def find_first_match(test_file_content):
      match_obj = re.search('\s?(([\"][^\"]*[\"]|[\'][^\']*[\'])\s+dluohs)', test_file_content) # search for 'should "name"'
      if not match_obj:
        return None
      test_name = match_obj.group(1)[::-1]
      return "%s%s%s" % ("/", test_name.replace("should", "").strip(), "/")


class BaseRubyTask(sublime_plugin.TextCommand):
  def load_config(self):
    s = sublime.load_settings("RubyTest.sublime-settings")
    global RUBY_UNIT; RUBY_UNIT = s.get("ruby_unit_exec").split()
    global ERB_EXEC; ERB_EXEC = s.get("erb_exec").split()
    global CUCUMBER_UNIT; CUCUMBER_UNIT = s.get("ruby_cucumber_exec").split()
    global RSPEC_UNIT; RSPEC_UNIT = s.get("ruby_rspec_exec").split()
    global RUBY_UNIT_FOLDER; RUBY_UNIT_FOLDER = s.get("ruby_unit_folder")
    global CUCUMBER_UNIT_FOLDER; CUCUMBER_UNIT_FOLDER = s.get("ruby_cucumber_folder")
    global RSPEC_UNIT_FOLDER; RSPEC_UNIT_FOLDER = s.get("ruby_rspec_folder")
    global USE_SCRATCH; USE_SCRATCH = s.get("ruby_use_scratch")

    if s.get("save_on_run"):
      self.window().run_command("save_all")

  def save_test_run(self, ex, file_name):
    s = sublime.load_settings("RubyTest.last-run")
    s.set("last_test_run", ex.join(" "))
    s.set("last_test_file", file_name)

    sublime.save_settings("RubyTest.last-run")

  def window(self):
    return self.view.window()

  def show_tests_panel(self, project_root = None):
    if not USE_SCRATCH:
      self.window().run_command("show_panel", {"panel": "output.exec"})

  class BaseFile(object):
    def __init__(self, file_name): 
      self.folder_name, self.file_name = os.path.split(file_name)
      self.absolute_path = file_name
    def verify_syntax_command(self): return None
    def possible_alternate_files(self): return []
    def run_all_tests_command(self): return None
    def get_project_root(self): return None
    def find_project_root(self, partition_folder):
      project_root, test_folder, file_name = self.absolute_path.partition(partition_folder)
      return project_root
    def relative_file_path(self, partition_folder):
      folder_name, _, file_name = self.absolute_path.partition(partition_folder)
      return partition_folder + file_name
    def get_current_line_number(self, view):
      char_under_cursor = view.sel()[0].a
      return view.rowcol(char_under_cursor)[0] + 1
    def features(self): return []

  class AnonymousFile(BaseFile):
    def __init__(self):
      True

  class RubyFile(BaseFile):
    def verify_syntax_command(self): return RUBY_UNIT + ["-c", self.absolute_path]
    def possible_alternate_files(self): return [self.file_name.replace(".rb", "_spec.rb"), self.file_name.replace(".rb", "_test.rb"), self.file_name.replace(".rb", ".feature")]
    def features(self): return ["verify_syntax", "switch_to_test", "rails_generate", "extract_variable"]

  class UnitFile(RubyFile):
    def possible_alternate_files(self): return [self.file_name.replace("_test.rb", ".rb")]
    def run_all_tests_command(self): return RUBY_UNIT + ["-Itest", self.relative_file_path(RUBY_UNIT_FOLDER)]
    def run_single_test_command(self, view):
      region = view.sel()[0]
      line_region = view.line(region)
      text_string = view.substr(sublime.Region(region.begin() - 2000, line_region.end()))
      text_string = text_string.replace("\n", "\\N")
      text_string = text_string[::-1]
      test_name = TestMethodMatcher().find_first_match_in(text_string)
      if test_name is None:
        sublime.error_message("No test name!")
        return
      return RUBY_UNIT + ["-Itest", self.relative_file_path(RUBY_UNIT_FOLDER), "-n", test_name]
    def features(self): return super(BaseRubyTask.UnitFile, self).features() + ["run_test"]
    def get_project_root(self): return self.find_project_root(RUBY_UNIT_FOLDER)

  class CucumberFile(BaseFile):
    def possible_alternate_files(self): return [self.file_name.replace(".feature", ".rb")]
    def run_all_tests_command(self): return CUCUMBER_UNIT + [self.relative_file_path(CUCUMBER_UNIT_FOLDER)]
    def run_single_test_command(self, view): return CUCUMBER_UNIT + [self.relative_file_path(CUCUMBER_UNIT_FOLDER), "-l" + str(self.get_current_line_number(view))]
    def features(self): return ["run_test"]
    def get_project_root(self): return self.find_project_root(CUCUMBER_UNIT_FOLDER)

  class RSpecFile(RubyFile):
    def possible_alternate_files(self): return [self.file_name.replace("_spec.rb", ".rb")]
    def run_all_tests_command(self): return RSPEC_UNIT + [self.relative_file_path(RSPEC_UNIT_FOLDER)]
    def run_single_test_command(self, view): return RSPEC_UNIT + [self.relative_file_path(RSPEC_UNIT_FOLDER), "-l" + str(self.get_current_line_number(view))]
    def features(self): return super(BaseRubyTask.RSpecFile, self).features() + ["run_test"]
    def get_project_root(self): return self.find_project_root(RSPEC_UNIT_FOLDER)

  class ErbFile(BaseFile):
    def verify_syntax_command(self): return ["sh", "-c", ERB_EXEC.join(" ") + " -xT - " + self.file_name + " | " + RUBY_UNIT + " -c"]
    def can_verify_syntax(self): return True
    def features(self): return ["verify_syntax"]

  def file_type(self, file_name = None):
    file_name = file_name or self.view.file_name()
    if not file_name: return BaseRubyTask.AnonymousFile()
    if re.search('\w+\_test.rb', file_name):
      return BaseRubyTask.UnitFile(file_name)
    elif re.search('\w+\_spec.rb', file_name):
      return BaseRubyTask.RSpecFile(file_name)
    elif re.search('\w+\.feature', file_name):
      return BaseRubyTask.CucumberFile(file_name)
    elif re.search('\w+\.rb', file_name):
      return BaseRubyTask.RubyFile(file_name)
    elif re.search('\w+\.erb', file_name):
      return BaseRubyTask.ErbFile(file_name)
    else:
      return BaseRubyTask.BaseFile(file_name)

class RunSingleRubyTest(BaseRubyTask):
  def is_enabled(self): return 'run_test' in self.file_type().features()
  def run(self, args):
    self.load_config()
    file = self.file_type()
    command = file.run_single_test_command(self.view)
    if command:
      self.save_test_run(command, file.file_name)
      self.view.window().run_command("exec", {
        "cmd": command,
        "working_dir": file.get_project_root(),
        "file_regex": r"([^ ]*\.rb):?(\d*)"
      })

class RunAllRubyTest(BaseRubyTask):
  def is_enabled(self): return 'run_test' in self.file_type().features()
  def run(self, args):
    self.load_config()
    file = self.file_type(self.view.file_name())
    command = file.run_all_tests_command()
    if command:
      self.save_test_run(command, file.file_name)
      self.view.window().run_command("exec", {
        "cmd": command,
        "working_dir": file.get_project_root(),
        "file_regex": r"([^ ]*\.rb):?(\d*)"
      })
    else:
      sublime.error_message("Only *_test.rb, *_spec.rb, *.feature files supported!")


class RunLastRubyTest(BaseRubyTask):
  def load_last_run(self):
    self.load_config()
    s = sublime.load_settings("RubyTest.last-run")
    return (s.get("last_test_run").split(), s.get("last_test_file"))

  def run(self, args):
    last_command, last_file = self.load_last_run()
    file = self.file_type(last_file)
    self.view.window().run_command("exec", {
      "cmd": last_command,
      "working_dir": file.get_project_root(),
      "file_regex": r"([^ ]*\.rb):?(\d*)"
    })

class VerifyRubyFile(BaseRubyTask):
  def is_enabled(self): return 'verify_syntax' in self.file_type().features()
  def run(self, args):
    self.load_config()
    file = self.file_type()
    command = file.verify_syntax_command()
    if command:
      self.view.window().run_command("exec", {
        "cmd": command,
        "working_dir": file.get_project_root(),
        "file_regex": r"([^ ]*\.rb):?(\d*)"
      })
    else:
      sublime.error_message("Only .rb or .erb files supported!")

class SwitchBetweenCodeAndTest(BaseRubyTask):
  def is_enabled(self): return 'switch_to_test' in self.file_type().features()
  def run(self, args, split_view):
    possible_alternates = self.file_type().possible_alternate_files()
    alternates = self.project_files(lambda file: file in possible_alternates)
    if alternates:
      if split_view:
        self.window().run_command('set_layout', {
                              "cols": [0.0, 0.5, 1.0],
                              "rows": [0.0, 1.0],
                              "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]
                          })
        self.window().focus_group(1)
      if len(alternates) == 1:
        self.window().open_file(alternates.pop())
      else:
        callback = functools.partial(self.on_selected, alternates)
        self.window().show_quick_panel(alternates, callback)
    else:
      sublime.error_message("could not find " + str(possible_alternates))

  def on_selected(self, alternates, index):
    if index == -1:
      return

    self.window().open_file(alternates[index])

  def walk(self, directory, ignored_directories = []):
    ignored_directories = ['.git', 'vendor']  # Move this into config
    for dir, dirnames, files in os.walk(directory):
      dirnames[:] = [dirname for dirname in dirnames if dirname not in ignored_directories]
      yield dir, dirnames, files

  def project_files(self, file_matcher):
    directories = self.window().folders()
    return [os.path.join(dirname, file) for directory in directories for dirname, _, files in self.walk(directory) for file in filter(file_matcher, files)]


class RubyRunShell(BaseRubyTask):
  def execute_command(self, command, caption = "Running shell command"):
    self.window().run_command("exec", {
        "cmd": command,
        "working_dir": self.window().folders()[0]
      })


class RubyRailsGenerate(BaseRubyTask):
  def is_enabled(self): return 'rails_generate' in self.file_type().features()

  def run(self, args, type = "migration"):
    self.window().show_input_panel("rails generate", type + " ", lambda s: self.generate(s), None, None)

  def generate(self, argument):
    command = ['rails', 'generate'] + argument.split()
    self.execute_command(command, "Generating" + argument)

class RubyExtractVariable(BaseRubyTask):
  def is_enabled(self): return 'extract_variable' in self.file_type().features()
  def run(self, args):
    for selection in self.view.sel():
      self.window().show_input_panel("Variable Name: ", '', lambda name: self.generate(selection, name), None, None)

  def generate(self, selection, name):
    extracted = self.view.substr(selection)
    line = self.view.line(selection)
    white_space = re.match("\s*", self.view.substr(line)).group()
    edit = self.view.begin_edit()
    try:
      self.view.replace(edit, selection, name)
      self.view.insert(edit, line.begin(), white_space + name + " = " + extracted + "\n")
    finally:
      self.view.end_edit(edit)
