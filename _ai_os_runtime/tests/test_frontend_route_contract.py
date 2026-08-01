from __future__ import annotations

import re
import unittest
from pathlib import Path


class FrontendRouteContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_root = Path(__file__).resolve().parents[1]
        cls.destinations = (
            cls.runtime_root / "ai-office-ui" / "src" / "app" / "destinations.ts"
        ).read_text(encoding="utf-8")
        cls.app = (
            cls.runtime_root / "ai-office-ui" / "src" / "app" / "App.tsx"
        ).read_text(encoding="utf-8")

    def test_every_terminal_function_has_an_explicit_component(self) -> None:
        registered = set(re.findall(r'path: "([^"]+)"', self.destinations))
        mapped = set(
            re.findall(
                r'^\s+"([^"]+)": \(\) => import',
                self.app,
                flags=re.MULTILINE,
            )
        )

        self.assertEqual(len(registered), 58)
        self.assertEqual(mapped, registered)

    def test_shared_terminals_derive_tab_from_pathname(self) -> None:
        relative_files = (
            "destinations/options/OptionsDesk.tsx",
            "destinations/scanners/Scanners.tsx",
        )
        for relative in relative_files:
            source = (
                self.runtime_root / "ai-office-ui" / "src" / relative
            ).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("useLocation", source)
                self.assertIn(
                    'location.pathname.split("/").filter(Boolean).slice(-1)[0]',
                    source,
                )
                self.assertNotIn("const params = useParams()", source)
                self.assertNotIn("const tab = params.tab", source)


    def test_every_frontend_api_path_has_backend_handler(self) -> None:
        data_root = self.runtime_root / "ai-office-ui" / "src" / "data"
        frontend = "\n".join(
            (data_root / filename).read_text(encoding="utf-8")
            for filename in ("queries.ts", "actions.ts")
        )
        backend = (
            self.runtime_root / "api" / "ai_os_api_server.py"
        ).read_text(encoding="utf-8")
        paths = set(re.findall(r'"(/api/[^"?]+)', frontend))

        self.assertEqual(len(paths), 71)
        self.assertEqual(
            sorted(path for path in paths if path not in backend),
            [],
        )



if __name__ == "__main__":
    unittest.main()
