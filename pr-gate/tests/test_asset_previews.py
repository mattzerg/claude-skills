#!/usr/bin/env python3
"""Tests for pr-gate asset preview classification + rendering + injection."""

from __future__ import annotations

import importlib.util
import io
import pathlib
import tempfile
import unittest
from unittest import mock


RUN_PATH = pathlib.Path(__file__).resolve().parents[1] / "run.py"
SPEC = importlib.util.spec_from_file_location("pr_gate_run", RUN_PATH)
pr_gate_run = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(pr_gate_run)


class ClassifyAssetsTest(unittest.TestCase):
    def test_buckets_each_kind(self):
        files = [
            "web/src/public/content/blog/welcome.md",
            "web/src/public/images/hero.png",
            "demos/loop.mp4",
            "web/src/pages/index.vue",
            "web/src/pages/Index.vue",
            "web/src/pages/pricing.tsx",
            "landing-pages/index.vue",
            "MattZerg/Writing/note.md",
            "src/lib/util.ts",  # code, ignored
            "Writing/landing-page-copy.md",
        ]
        status = {f: "M" for f in files}
        out = pr_gate_run.classify_assets(files, status)

        self.assertIn("web/src/public/content/blog/welcome.md", out["blog"])
        self.assertIn("MattZerg/Writing/note.md", out["blog"])
        self.assertIn("web/src/public/images/hero.png", out["images"])
        self.assertIn("demos/loop.mp4", out["videos"])
        self.assertIn("web/src/pages/index.vue", out["landing"])
        self.assertIn("web/src/pages/Index.vue", out["landing"])
        self.assertIn("web/src/pages/pricing.tsx", out["landing"])
        self.assertIn("landing-pages/index.vue", out["landing"])
        self.assertIn("Writing/landing-page-copy.md", out["copy"])
        self.assertNotIn("src/lib/util.ts", sum(out.values(), []))

    def test_deleted_files_are_dropped(self):
        files = ["web/src/public/images/old.png"]
        status = {"web/src/public/images/old.png": "D"}
        out = pr_gate_run.classify_assets(files, status)
        self.assertEqual(out["images"], [])


class FrontmatterTest(unittest.TestCase):
    def test_parses_flat_kv(self):
        text = (
            "---\n"
            'title: "Welcome"\n'
            "description: A hello post\n"
            "hero: /images/hero.png\n"
            "---\n\n"
            "Body starts here.\n"
        )
        fm, body = pr_gate_run.parse_frontmatter(text)
        self.assertEqual(fm["title"], "Welcome")
        self.assertEqual(fm["description"], "A hello post")
        self.assertEqual(fm["hero"], "/images/hero.png")
        self.assertTrue(body.startswith("Body starts here"))

    def test_no_frontmatter(self):
        text = "Just a body, no fm."
        fm, body = pr_gate_run.parse_frontmatter(text)
        self.assertEqual(fm, {})
        self.assertEqual(body, text)

    def test_first_words_strips_html_angle_brackets(self):
        out = pr_gate_run.first_words("<div>Hello</div> world")

        self.assertEqual(out, "Hello world")
        self.assertNotIn("div", out)


class BuildPreviewsTest(unittest.TestCase):
    def test_returns_none_when_empty(self):
        empty = {"images": [], "videos": [], "blog": [], "landing": [], "copy": []}
        self.assertIsNone(
            pr_gate_run.build_asset_previews(
                pathlib.Path("/tmp"), "main", empty, "owner", "repo", "branch",
            )
        )

    def test_image_renders_inline_with_raw_url(self):
        assets = {
            "images": ["docs/hero.png"],
            "videos": [], "blog": [], "landing": [], "copy": [],
        }
        out = pr_gate_run.build_asset_previews(
            pathlib.Path("/tmp"), "main", assets, "ownerx", "repox", "branchy",
        )
        self.assertIn(
            "https://raw.githubusercontent.com/ownerx/repox/branchy/docs/hero.png",
            out,
        )
        self.assertIn("📎 Asset previews", out)
        self.assertIn("<details>", out)

    def test_image_preview_escapes_filename_html(self):
        assets = {
            "images": ['docs/bad"name<.png'],
            "videos": [], "blog": [], "landing": [], "copy": [],
        }
        out = pr_gate_run.build_asset_previews(
            pathlib.Path("/tmp"), "main", assets, "ownerx", "repox", "branchy",
        )
        self.assertIn("bad%22name%3C.png", out)
        self.assertIn("alt=\"bad&quot;name&lt;.png\"", out)
        self.assertIn("docs/bad&quot;name&lt;.png", out)

    def test_svg_is_classified_as_image(self):
        files = ["docs/diagram.svg"]
        status = {"docs/diagram.svg": "A"}
        out = pr_gate_run.classify_assets(files, status)

        self.assertIn("docs/diagram.svg", out["images"])

    def test_branch_name_is_url_encoded_in_preview_urls(self):
        assets = {
            "images": ["docs/hero.png"],
            "videos": [], "blog": [], "landing": [], "copy": [],
        }
        out = pr_gate_run.build_asset_previews(
            pathlib.Path("/tmp"), "main", assets, "ownerx", "repox", "feature/fix #1",
        )
        self.assertIn("feature/fix%20%231/docs/hero.png", out)

    def test_video_branch_name_is_url_encoded_in_preview_urls(self):
        assets = {
            "images": [], "videos": ["demos/loop.mp4"],
            "blog": [], "landing": [], "copy": [],
        }
        out = pr_gate_run.build_asset_previews(
            pathlib.Path("/tmp"), "main", assets, "ownerx", "repox", "feature/fix #1",
        )
        self.assertIn("feature/fix%20%231/demos/loop.mp4", out)

    def test_blog_excerpt_includes_title_and_description(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            blog = root / "blog" / "post.md"
            blog.parent.mkdir(parents=True)
            blog.write_text(
                "---\n"
                'title: "How Loops Work"\n'
                "description: A short explainer\n"
                "hero: /img/loop-hero.png\n"
                "---\n\n"
                "Loops repeat. They keep repeating until you say stop.\n"
            )
            assets = {
                "images": [], "videos": [],
                "blog": ["blog/post.md"],
                "landing": [], "copy": [],
            }
            out = pr_gate_run.build_asset_previews(
                root, "main", assets, "ownerx", "repox", "branchy",
            )
            self.assertIn("How Loops Work", out)
            self.assertIn("A short explainer", out)
            self.assertIn(
                "https://raw.githubusercontent.com/ownerx/repox/branchy/img/loop-hero.png",
                out,
            )
            self.assertIn("Loops repeat", out)

    def test_blog_hero_url_is_html_escaped(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            blog = root / "blog" / "post.md"
            blog.parent.mkdir(parents=True)
            blog.write_text(
                "---\n"
                "title: Hero Escape\n"
                "hero: https://cdn.example.com/img.png\" onerror=\"bad\n"
                "---\n\n"
                "Body.\n"
            )
            assets = {
                "images": [], "videos": [],
                "blog": ["blog/post.md"],
                "landing": [], "copy": [],
            }
            out = pr_gate_run.build_asset_previews(
                root, "main", assets, "ownerx", "repox", "branchy",
            )

            self.assertIn("https://cdn.example.com/img.png&quot; onerror=&quot;bad", out)
            self.assertNotIn('onerror="bad', out)

    def test_landing_overflow_is_called_out(self):
        assets = {
            "images": [], "videos": [], "blog": [],
            "landing": [f"web/src/pages/page-{i}.vue" for i in range(12)],
            "copy": [],
        }
        out = pr_gate_run.build_asset_previews(
            pathlib.Path("/tmp"), "main", assets, "ownerx", "repox", "branchy",
        )

        self.assertIn("_+2 more landing page(s) not shown_", out)

    def test_blog_without_frontmatter_uses_stem_and_body_excerpt(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            blog = root / "blog" / "plain-post.md"
            blog.parent.mkdir(parents=True)
            blog.write_text("No frontmatter here, just the post body.")
            assets = {
                "images": [], "videos": [],
                "blog": ["blog/plain-post.md"],
                "landing": [], "copy": [],
            }
            out = pr_gate_run.build_asset_previews(
                root, "main", assets, "ownerx", "repox", "branchy",
            )
            self.assertIn("Blog: plain-post", out)
            self.assertIn("No frontmatter here", out)

    def test_copy_overflow_is_called_out(self):
        assets = {
            "images": [], "videos": [], "blog": [], "landing": [],
            "copy": [f"copy/doc-{i}.md" for i in range(6)],
        }
        diff = "diff --git a/x b/x\n@@ -1 +1 @@\n-old\n+new\n"
        result = pr_gate_run.subprocess.CompletedProcess(["git"], 0, stdout=diff, stderr="")
        with mock.patch.object(pr_gate_run.subprocess, "run", return_value=result):
            out = pr_gate_run.build_asset_previews(
                pathlib.Path("/tmp"), "main", assets, "ownerx", "repox", "branchy",
            )

        self.assertIn("_+2 more copy file(s) not shown_", out)


class InjectPreviewsTest(unittest.TestCase):
    def test_prepends_to_body_value(self):
        passthrough = ["--title", "feat: x", "--body", "## Why\nbecause"]
        with tempfile.TemporaryDirectory() as td:
            out, injected = pr_gate_run.inject_asset_previews(
                passthrough, "PREVIEW_BLOCK\n", pathlib.Path(td),
            )
        self.assertTrue(injected)
        body_idx = out.index("--body") + 1
        self.assertTrue(out[body_idx].startswith("PREVIEW_BLOCK\n"))
        self.assertIn("## Why\nbecause", out[body_idx])

    def test_prepends_to_body_equals_form(self):
        passthrough = ["--title=t", "--body=existing"]
        with tempfile.TemporaryDirectory() as td:
            out, injected = pr_gate_run.inject_asset_previews(
                passthrough, "PRE\n", pathlib.Path(td),
            )
        self.assertTrue(injected)
        body_arg = next(a for a in out if a.startswith("--body="))
        self.assertTrue(body_arg.startswith("--body=PRE\n"))
        self.assertIn("existing", body_arg)

    def test_rewrites_body_file_via_tmp(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            src = tmp / "body.md"
            src.write_text("ORIGINAL")
            passthrough = ["--body-file", str(src)]
            out, injected = pr_gate_run.inject_asset_previews(
                passthrough, "PREVIEW\n", tmp / "scratch",
            )
            self.assertTrue(injected)
            new_path = pathlib.Path(out[out.index("--body-file") + 1])
            self.assertNotEqual(new_path, src)
            self.assertEqual(src.read_text(), "ORIGINAL")  # untouched
            self.assertTrue(new_path.read_text().startswith("PREVIEW\n"))
            self.assertIn("ORIGINAL", new_path.read_text())

    def test_rewrites_body_file_equals_form_via_tmp(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            src = tmp / "body.md"
            src.write_text("ORIGINAL")
            passthrough = [f"--body-file={src}"]
            out, injected = pr_gate_run.inject_asset_previews(
                passthrough, "PREVIEW\n", tmp / "scratch",
            )
            self.assertTrue(injected)
            body_arg = next(a for a in out if a.startswith("--body-file="))
            new_path = pathlib.Path(body_arg[len("--body-file="):])
            self.assertNotEqual(new_path, src)
            self.assertEqual(src.read_text(), "ORIGINAL")
            self.assertTrue(new_path.read_text().startswith("PREVIEW\n"))
            self.assertIn("ORIGINAL", new_path.read_text())

    def test_body_file_read_error_warns_for_preview_injection(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            body_dir = tmp / "body-dir"
            body_dir.mkdir()
            stderr = io.StringIO()
            with mock.patch("sys.stderr", stderr):
                out, injected = pr_gate_run.inject_asset_previews(
                    ["--body-file", str(body_dir)], "PREVIEW\n", tmp / "scratch",
                )

            self.assertFalse(injected)
            self.assertEqual(out, ["--body-file", str(body_dir)])
            self.assertIn("could not read", stderr.getvalue())
            self.assertIn("asset preview injection", stderr.getvalue())

    def test_no_body_arg_returns_not_injected(self):
        passthrough = ["--title", "no body here"]
        with tempfile.TemporaryDirectory() as td:
            out, injected = pr_gate_run.inject_asset_previews(
                passthrough, "PRE", pathlib.Path(td),
            )
        self.assertFalse(injected)
        self.assertEqual(out, passthrough)


if __name__ == "__main__":
    unittest.main()
