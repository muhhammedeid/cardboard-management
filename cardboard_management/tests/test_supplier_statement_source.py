import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).parents[1] / 'reporting.py'


class TestSupplierStatementSource(unittest.TestCase):
    def test_statement_is_a_dedicated_typed_timeline_contract(self):
        source = SOURCE.read_text(encoding='utf-8')
        tree = ast.parse(source)
        statement = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'get_supplier_statement')
        self.assertNotEqual(ast.unparse(statement.body[0]), 'return get_supplier_summary(supplier, from_date, to_date)')
        self.assertIn('"entries"', ast.get_source_segment(source, statement))
        self.assertIn('sorted(', ast.get_source_segment(source, statement))
        self.assertNotIn('running_balance', ast.get_source_segment(source, statement))


if __name__ == '__main__':
    unittest.main()
