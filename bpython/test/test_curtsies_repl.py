# coding: utf8
import code
from contextlib import contextmanager
from functools import partial
from mock import Mock, patch
import os
from StringIO import StringIO
import sys
import tempfile

import unittest
try:
    from unittest import skip
except ImportError:
    def skip(f):
        return lambda self: None

py3 = (sys.version_info[0] == 3)

from bpython.curtsiesfrontend import repl as curtsiesrepl
from bpython.curtsiesfrontend import interpreter
from bpython import autocomplete
from bpython import config
from bpython import args

def setup_config(conf):
    config_struct = config.Struct()
    config.loadini(config_struct, os.devnull)
    for key, value in conf.items():
        if not hasattr(config_struct, key):
            raise ValueError("%r is not a valid config attribute" % (key,))
        setattr(config_struct, key, value)
    return config_struct


class TestCurtsiesRepl(unittest.TestCase):

    def setUp(self):
        self.repl = create_repl()

    def cfwp(self, source):
        return interpreter.code_finished_will_parse(source, self.repl.interp.compile)

    def test_code_finished_will_parse(self):
        self.repl.buffer = ['1 + 1']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (True, True))
        self.repl.buffer = ['def foo(x):']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (False, True))
        self.repl.buffer = ['def foo(x)']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (True, False))
        self.repl.buffer = ['def foo(x):', 'return 1']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (True, False))
        self.repl.buffer = ['def foo(x):', '    return 1']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (True, True))
        self.repl.buffer = ['def foo(x):', '    return 1', '']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (True, True))

    def test_external_communication(self):
        self.assertEqual(type(self.repl.help_text()), type(b''))
        self.repl.send_current_block_to_external_editor()
        self.repl.send_session_to_external_editor()

    def test_external_communication_encoding(self):
        with captured_output():
            self.repl.display_lines.append(u'>>> "åß∂ƒ"')
            self.repl.send_session_to_external_editor()

    def test_get_last_word(self):
        self.repl.rl_history.entries=['1','2 3','4 5 6']
        self.repl._set_current_line('abcde')
        self.repl.get_last_word()
        self.assertEqual(self.repl.current_line,'abcde6')
        self.repl.get_last_word()
        self.assertEqual(self.repl.current_line,'abcde3')

    @skip # this is the behavior of bash - not currently implemented
    def test_get_last_word_with_prev_line(self):
        self.repl.rl_history.entries=['1','2 3','4 5 6']
        self.repl._set_current_line('abcde')
        self.repl.up_one_line()
        self.assertEqual(self.repl.current_line,'4 5 6')
        self.repl.get_last_word()
        self.assertEqual(self.repl.current_line,'4 5 63')
        self.repl.get_last_word()
        self.assertEqual(self.repl.current_line,'4 5 64')
        self.repl.up_one_line()
        self.assertEqual(self.repl.current_line,'2 3')


class TestCurtsiesReplTab(unittest.TestCase):

    def setUp(self):
        self.repl = create_repl()
        self.repl.matches_iter = Mock()
        def add_matches(*args, **kwargs):
            self.repl.matches_iter.matches = ['aaa', 'aab', 'aac']
        self.repl.complete = Mock(side_effect=add_matches,
                                  return_value=True)

    def test_tab_with_no_matches_triggers_completion(self):
        self.repl._current_line = ' asdf'
        self.repl._cursor_offset = 5
        self.repl.matches_iter.matches = []
        self.repl.matches_iter.is_cseq.return_value = False
        self.repl.matches_iter.cur_line.return_value = (None, None)
        self.repl.on_tab()
        self.repl.complete.assert_called_once_with(tab=True)

    def test_tab_after_indentation_adds_space(self):
        self.repl._current_line = '    '
        self.repl._cursor_offset = 4
        self.repl.on_tab()
        self.assertEqual(self.repl._current_line, '        ')
        self.assertEqual(self.repl._cursor_offset, 8)

    def test_tab_at_beginning_of_line_adds_space(self):
        self.repl._current_line = ''
        self.repl._cursor_offset = 0
        self.repl.on_tab()
        self.assertEqual(self.repl._current_line, '    ')
        self.assertEqual(self.repl._cursor_offset, 4)

    def test_tab_with_no_matches_selects_first(self):
        self.repl._current_line = ' aa'
        self.repl._cursor_offset = 3
        self.repl.matches_iter.matches = []
        self.repl.matches_iter.is_cseq.return_value = False
        self.repl.matches_iter.next.return_value = None
        self.repl.matches_iter.__next__.return_value = None
        self.repl.matches_iter.cur_line.return_value = (None, None)
        self.repl.on_tab()
        self.repl.complete.assert_called_once_with(tab=True)
        self.repl.matches_iter.cur_line.assert_called_once_with()

    def test_tab_with_matches_selects_next_match(self):
        self.repl._current_line = ' aa'
        self.repl._cursor_offset = 3
        self.repl.complete()
        self.repl.matches_iter.is_cseq.return_value = False
        self.repl.matches_iter.next.return_value = None
        self.repl.matches_iter.__next__.return_value = None
        self.repl.matches_iter.cur_line.return_value = (None, None)
        self.repl.on_tab()
        self.repl.matches_iter.cur_line.assert_called_once_with()

    def test_tab_completes_common_sequence(self):
        self.repl._current_line = ' a'
        self.repl._cursor_offset = 2
        self.repl.matches_iter.matches = ['aaa', 'aab', 'aac']
        self.repl.matches_iter.is_cseq.return_value = True
        self.repl.matches_iter.substitute_cseq.return_value = (None, None)
        self.repl.on_tab()
        self.repl.matches_iter.substitute_cseq.assert_called_once_with()


class TestCurtsiesReplFilenameCompletion(unittest.TestCase):
    def setUp(self):
        self.repl = create_repl()

    def test_list_win_visible_and_match_selected_on_tab_when_multiple_options(self):
        self.repl._current_line = " './'"
        self.repl._cursor_offset = 2
        with patch('bpython.autocomplete.get_completer_bpython') as mock:
            mock.return_value = (['./abc', './abcd', './bcd'],
                                 autocomplete.FilenameCompletion())
            self.repl.update_completion()
            self.assertEqual(self.repl.list_win_visible, False)
            self.repl.on_tab()
        self.assertEqual(self.repl.current_match, './abc')
        self.assertEqual(self.repl.list_win_visible, True)

    def test_list_win_not_visible_and_cseq_if_cseq(self):
        self.repl._current_line = " './a'"
        self.repl._cursor_offset = 5
        with patch('bpython.autocomplete.get_completer_bpython') as mock:
            mock.return_value = (['./abcd', './abce'],
                                 autocomplete.FilenameCompletion())
            self.repl.update_completion()
            self.assertEqual(self.repl.list_win_visible, False)
        self.repl.on_tab()
        self.assertEqual(self.repl._current_line, " './abc'")
        self.assertEqual(self.repl.current_match, None)
        self.assertEqual(self.repl.list_win_visible, False)

    def test_list_win_not_visible_and_match_selected_if_one_option(self):
        self.repl._current_line = " './a'"
        self.repl._cursor_offset = 5
        with patch('bpython.autocomplete.get_completer_bpython') as mock:
            mock.return_value = (['./abcd'], autocomplete.FilenameCompletion())
            self.repl.update_completion()
            self.assertEqual(self.repl.list_win_visible, False)
        self.repl.on_tab()
        self.assertEqual(self.repl._current_line, " './abcd'")
        self.assertEqual(self.repl.current_match, None)
        self.assertEqual(self.repl.list_win_visible, False)


@contextmanager # from http://stackoverflow.com/a/17981937/398212 - thanks @rkennedy
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err

def create_repl(**kwargs):
    config = setup_config({'editor':'true'})
    repl = curtsiesrepl.Repl(config=config, **kwargs)
    os.environ['PAGER'] = 'true'
    repl.width = 50
    repl.height = 20
    return repl

class TestFutureImports(unittest.TestCase):

    def test_repl(self):
        repl = create_repl()
        with captured_output() as (out, err):
            repl.push('from __future__ import division')
            repl.push('1 / 2')
        self.assertEqual(out.getvalue(), '0.5\n')

    def test_interactive(self):
        interp = code.InteractiveInterpreter(locals={})
        with captured_output() as (out, err):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py') as f:
                f.write('from __future__ import division\n')
                f.write('print(1/2)\n')
                f.flush()
                args.exec_code(interp, [f.name])

            repl = create_repl(interp=interp)
            repl.push('1 / 2')

        self.assertEqual(out.getvalue(), '0.5\n0.5\n')

class TestPredictedIndent(unittest.TestCase):
    def setUp(self):
        self.repl = create_repl()

    def test_simple(self):
        self.assertEqual(self.repl.predicted_indent(''), 0)
        self.assertEqual(self.repl.predicted_indent('class Foo:'), 4)
        self.assertEqual(self.repl.predicted_indent('class Foo: pass'), 0)
        self.assertEqual(self.repl.predicted_indent('def asdf():'), 4)
        self.assertEqual(self.repl.predicted_indent('def asdf(): return 7'), 0)

    @skip
    def test_complex(self):
        self.assertEqual(self.repl.predicted_indent('[a,'), 1)
        self.assertEqual(self.repl.predicted_indent('reduce(asdfasdf,'), 7)


if __name__ == '__main__':
    unittest.main()
