from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from .coding_tools import CodingWorkspace
from .git_tools import GitWorkspace
from .local_files import LocalFiles


class CodingStage(str, Enum):
    UNDERSTAND = 'UNDERSTAND'
    PLAN = 'PLAN'
    APPROVAL = 'APPROVAL'
    EDIT = 'EDIT'
    TEST = 'TEST'
    REVIEW = 'REVIEW'
    DIFF = 'DIFF'
    VERIFY = 'VERIFY'
    COMPLETE = 'COMPLETE'
    FAILED = 'FAILED'


@dataclass
class CodingRun:
    project_dir: str
    objective: str
    stage: CodingStage = CodingStage.UNDERSTAND
    plan: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    backups: list[str] = field(default_factory=list)
    test_result: dict = field(default_factory=dict)
    diff: str = ''
    verification: dict = field(default_factory=dict)
    error: str = ''

    def as_dict(self) -> dict:
        data = asdict(self)
        data['stage'] = self.stage.value
        return data


class CodingAgentV2:
    """Coordinator over existing approved file/Git/test primitives.

    This class does not expose arbitrary shell commands and does not invent code. The
    caller supplies a reviewed mapping of complete file contents after planning.
    """

    def __init__(self, files: LocalFiles | None = None) -> None:
        self.files = files or LocalFiles()
        self.coding = CodingWorkspace(self.files)
        self.git = GitWorkspace(self.files)

    def inspect(self, project_dir: str, objective: str, *, max_items: int = 300) -> CodingRun:
        run = CodingRun(str(Path(project_dir)), str(objective).strip())
        tree = self.coding.tree(project_dir, max_items)
        run.stage = CodingStage.PLAN
        run.plan = [
            f'Inspect approved project tree ({len(tree.get("items", [])) if isinstance(tree, dict) else "unknown"} items).',
            'Identify the smallest files/tests required for the objective.',
            'Require explicit edit approval before writing supplied changes.',
            'Write with existing backup behavior.',
            'Run allowlisted Python unittest discovery.',
            'Inspect Git diff.',
            'Verify tests and expected changed files before completion.',
        ]
        return run

    def apply_reviewed_changes(
        self,
        run: CodingRun,
        changes: dict[str, str],
        *,
        explicit_edit_approval: bool,
        test_timeout: int = 180,
    ) -> CodingRun:
        if not explicit_edit_approval:
            run.stage = CodingStage.APPROVAL
            run.error = 'Explicit coding edit approval is required.'
            return run
        if not changes:
            run.stage = CodingStage.FAILED
            run.error = 'No reviewed file changes were supplied.'
            return run
        project = Path(run.project_dir).expanduser().resolve()
        try:
            run.stage = CodingStage.EDIT
            for relative, content in changes.items():
                target = (project / relative).resolve()
                if project != target and project not in target.parents:
                    raise PermissionError(f'Edit escaped project root: {relative}')
                result = self.coding.write_text(str(target), str(content))
                run.changed_files.append(str(target))
                backup = result.get('backup') if isinstance(result, dict) else None
                if backup:
                    run.backups.append(str(backup))

            run.stage = CodingStage.TEST
            result = self.coding.run_unit_tests(str(project), test_timeout)
            run.test_result = result if isinstance(result, dict) else {'result': result}

            run.stage = CodingStage.DIFF
            try:
                diff = self.git.diff(str(project), False)
                run.diff = diff if isinstance(diff, str) else json.dumps(diff, ensure_ascii=False, default=str)
            except Exception as exc:
                run.diff = f'Git diff unavailable: {type(exc).__name__}: {exc}'

            run.stage = CodingStage.VERIFY
            test_ok = bool(run.test_result.get('ok')) if 'ok' in run.test_result else run.test_result.get('returncode') == 0
            existing = [path for path in run.changed_files if Path(path).exists()]
            run.verification = {
                'tests_passed': test_ok,
                'changed_files_exist': len(existing) == len(run.changed_files),
                'changed_files': len(run.changed_files),
                'diff_available': not run.diff.startswith('Git diff unavailable:'),
            }
            run.stage = CodingStage.COMPLETE if test_ok and run.verification['changed_files_exist'] else CodingStage.FAILED
            if run.stage == CodingStage.FAILED:
                run.error = 'Coding verification failed; inspect tests/diff and restore backups if required.'
            return run
        except Exception as exc:
            run.stage = CodingStage.FAILED
            run.error = f'{type(exc).__name__}: {exc}'
            return run
