# Prompt note: the upload decision page

**Excerpt of the key prompt given to Claude Code:**

> "Which function in my upload decision script takes one clip and returns the decision, findings, validation_status and trace URL? Show me its name and what it needs as input"

No function returned all four. Claude Code was then told to go ahead with adding it to the script and building the page against `Upload Decision Page Sign-Off Criteria.md`.

## Checked against the criteria

- The news report (the video matched to CLIP-007, `is_news_report` ticked) returned **restrict, age restricted, 3 of 3 runs**, with NEWS-01 cited and four timed findings: [screenshot](news_report_screenshot.jpg).
- An answer that always fails the Pydantic check showed `routed_to_human_review` and no label (`src/demo_failed_check.py`).
- A violent clip (the video matched to CLIP-001) returned **remove, 3 of 3 runs**, VIO-01 at 00:00:02 to 00:00:45.
- Traces arrived in LangSmith project `youtube-upload-decisions`.

## Changed or rejected

- **Rejected: one finding for the whole news report.** The first answer gave a window of 00:00:12 to 00:03:15. The prompt now asks for a separate finding for each harmful moment, and the next answer gave three harm windows.
- **Changed: `rule_id` is always one ID.** Two of three runs first answered `NEWS-01 + NEWS-02`, copied from the policy's wording. The check caught both and the retry fixed them. The prompt now says so up front.
- **Changed: NEWS-01 can be cited in a finding** but still can't decide a clip, because policy v1.0 makes it a test.
- **Rejected: telling Gemini "a news report can't be remove".** That would push it into a softer label. A remove on a news report is kept in the log and sent to a human, with no label shown.
- **Rejected: sending pictures to LangSmith.** They can be stills of real violence. Traces hold the text, frame times, replies, errors and token counts.
- **Added after feedback: the reviewer's final call.** Tested in the browser on the test-mode page and checked on the LangSmith trace. The first design had the form on every clip's page; it was moved to its own page for routed clips, because its allow, restrict and remove choices would have put labels on an unvalidated answer.
- **Not done: running all 12 clips through the page.** It was suggested as optional and left out, so there is no results table.
- The screenshot was taken before the final call form was added. It has the page's "Blur pictures" box ticked, because frames are not published in this repo.
