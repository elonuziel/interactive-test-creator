"""Tests for DOCX intake and conversion flow in quiz_builder_cli.py."""

import builtins
import importlib.util
import os
from pathlib import Path


def _load_cli_module():
    root = Path(__file__).resolve().parents[1]
    cli_path = root / 'quiz_builder_cli.py'
    spec = importlib.util.spec_from_file_location('quiz_builder_cli', str(cli_path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_convert_docx_batch_skips_existing_pdf_without_overwrite(tmp_path):
    cli = _load_cli_module()

    docx = tmp_path / 'exam.docx'
    docx.write_text('fake', encoding='utf-8')
    existing_pdf = tmp_path / 'exam.pdf'
    existing_pdf.write_text('pdf', encoding='utf-8')

    summary = cli.convert_docx_batch(
        ['exam.docx'],
        str(tmp_path),
        backend_name='soffice',
        backend_value='soffice',
        overwrite_existing=False,
    )

    assert not summary['converted']
    assert summary['skipped'] == [('exam.docx', 'matching PDF already exists')]
    assert not summary['failed']


def test_convert_docx_batch_overwrite_uses_backend(tmp_path, monkeypatch):
    cli = _load_cli_module()

    docx = tmp_path / 'exam.docx'
    docx.write_text('fake', encoding='utf-8')
    existing_pdf = tmp_path / 'exam.pdf'
    existing_pdf.write_text('old', encoding='utf-8')

    called = {'count': 0}

    def fake_soffice(_soffice_path, _docx_path, _output_dir):
        called['count'] += 1
        (tmp_path / 'exam.pdf').write_text('new', encoding='utf-8')
        return True, 'ok'

    monkeypatch.setattr(cli, 'convert_docx_to_pdf_with_soffice', fake_soffice)

    summary = cli.convert_docx_batch(
        ['exam.docx'],
        str(tmp_path),
        backend_name='soffice',
        backend_value='soffice',
        overwrite_existing=True,
    )

    assert called['count'] == 1
    assert summary['converted'] == [('exam.docx', 'exam.pdf')]
    assert not summary['skipped']
    assert not summary['failed']


def test_process_workspace_fallback_when_no_converter_and_no_pdf(tmp_path, monkeypatch):
    cli = _load_cli_module()

    test_dir = tmp_path / 'workspace'
    test_dir.mkdir()
    (test_dir / 'only.docx').write_text('docx', encoding='utf-8')

    calls = []

    monkeypatch.setattr(cli, 'detect_docx_converter', lambda: (None, None))
    monkeypatch.setattr(cli, 'open_in_explorer', lambda _p: None)
    monkeypatch.setattr(cli, 'run_script', lambda *args, **kwargs: calls.append((args, kwargs)) or 0)

    answers = iter(['', ''])  # convert yes, continue after manual export prompt
    monkeypatch.setattr(builtins, 'input', lambda _prompt='': next(answers))

    cli.process_workspace('ws', str(test_dir))

    # No PDF exists after manual fallback -> should return before running pipeline scripts
    assert calls == []


def test_process_workspace_prefers_converted_pdf(tmp_path, monkeypatch):
    cli = _load_cli_module()

    test_dir = tmp_path / 'workspace'
    test_dir.mkdir()
    (test_dir / 'z.docx').write_text('docx', encoding='utf-8')
    (test_dir / 'a.pdf').write_text('existing', encoding='utf-8')

    script_calls = []

    monkeypatch.setattr(cli, 'detect_docx_converter', lambda: ('soffice', 'soffice'))
    monkeypatch.setattr(cli, 'open_in_explorer', lambda _p: None)
    monkeypatch.setattr(cli, 'is_pdf_digital', lambda _p: False)
    monkeypatch.setattr(cli, 'run_step6', lambda *_args, **_kwargs: None)

    def fake_convert_batch(docx_files, work_dir, backend_name, backend_value, overwrite_existing=False):
        assert docx_files == ['z.docx']
        assert backend_name == 'soffice'
        assert overwrite_existing is False
        (Path(work_dir) / 'z.pdf').write_text('converted', encoding='utf-8')
        return {
            'converted': [('z.docx', 'z.pdf')],
            'skipped': [],
            'failed': [],
        }

    monkeypatch.setattr(cli, 'convert_docx_batch', fake_convert_batch)

    def fake_run_script(name, args):
        script_calls.append((name, args))
        return 0

    monkeypatch.setattr(cli, 'run_script', fake_run_script)

    # convert yes, form number default 0, skip step3, skip prompt helper
    answers = iter(['', '', 's', 's'])
    monkeypatch.setattr(builtins, 'input', lambda _prompt='': next(answers))

    cli.process_workspace('ws', str(test_dir))

    assert script_calls[0][0] == '1_detect_pdf_type.py'
    assert script_calls[0][1][0].endswith(os.path.join('workspace', 'z.pdf'))
    assert ('4_extract_csv_answers.py', ['none', '0', '-o', os.path.join(str(test_dir), 'answers.json')]) in script_calls
