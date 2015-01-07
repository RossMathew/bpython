from bpython import autocomplete

import mock
import unittest
try:
    from unittest import skip
except ImportError:
    def skip(f):
        return lambda self: None

#TODO: Parts of autocompletion to test:
# Test that the right matches come back from find_matches (test that priority is correct)
# Test the various complete methods (import, filename) to see if right matches
# Test that MatchesIterator.substitute correctly subs given a match and a completer

class TestSafeEval(unittest.TestCase):
    def test_catches_syntax_error(self):
        self.assertRaises(autocomplete.EvaluationError,
                          autocomplete.safe_eval, '1re', {})


class TestFormatters(unittest.TestCase):

    def test_filename(self):
        last_part_of_filename = autocomplete.FilenameCompletion.format
        self.assertEqual(last_part_of_filename('abc'), 'abc')
        self.assertEqual(last_part_of_filename('abc/'), 'abc/')
        self.assertEqual(last_part_of_filename('abc/efg'), 'efg')
        self.assertEqual(last_part_of_filename('abc/efg/'), 'efg/')
        self.assertEqual(last_part_of_filename('/abc'), 'abc')
        self.assertEqual(last_part_of_filename('ab.c/e.f.g/'), 'e.f.g/')

    def test_attribute(self):
        self.assertEqual(autocomplete.after_last_dot('abc.edf'), 'edf')

class TestGetMatches(unittest.TestCase):

    def completer(self, matches, ):
        mock_completer = autocomplete.BaseCompletionType()
        mock_completer.matches = mock.Mock(return_value=matches)
        return mock_completer

    def test_no_completers(self):
        self.assertEqual(autocomplete.get_matches([]), [])

    def test_one_completer_without_matches_returns_empty_list(self):
        mock_completer = self.completer([])
        self.assertEqual(autocomplete.get_matches([mock_completer]), [])

    def test_one_completer_returns_matches(self):
        mock_completer = self.completer(['a'])
        self.assertEqual(autocomplete.get_matches([mock_completer]), ['a'])

    def test_two_completers_with_matches_returns_first_matches(self):
        a = self.completer(['a'])
        b = self.completer(['b'])
        self.assertEqual(autocomplete.get_matches([a, b]), ['a'])

    def test_first_non_none_completer_matches_are_returned(self):
        a = self.completer([])
        b = self.completer(['a'])
        self.assertEqual(autocomplete.get_matches([a, b]), [])

    def test_only_completer_returns_None(self):
        a = self.completer(None)
        self.assertEqual(autocomplete.get_matches([a]), [])

    def test_first_completer_returns_None(self):
        a = self.completer(None)
        b = self.completer(['a'])
        self.assertEqual(autocomplete.get_matches([a, b]), ['a'])

