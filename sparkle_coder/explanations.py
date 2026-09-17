"""Plain-language explanations from observed errors, without inventing a cause."""

import re

from .verification import active_checks


def check_title(command):
    if "tokenizer" in command or "vocab_size" in command:
        return "Text reader and model checks"
    if "unittest" in command or "pytest" in command or re.search(r"\btest\b", command):
        return "Project tests"
    if "build" in command:
        return "Build the project"
    if "lint" in command or "typecheck" in command or "tsc" in command:
        return "Code quality check"
    return "Project check"


def explain_failure(check):
    output = str(check.get("output") or check.get("error") or "")
    result = {"title": "A check needs attention", "what_happened": "A project check did not pass.",
              "meaning": "The saved project still needs testing or a repair before it is ready.",
              "next_step": "Choose Try fixing it. SPARKLE CODER will inspect the error and try a different repair.",
              "can_auto_fix": True, "kind": "check", "check_ids": [check.get("id")],
              "technical_details": output}
    mismatch = re.search(r"Expected vocab\s+(\d+),\s*got\s+(\d+)", output, re.I)
    module = re.search(r"(?:ModuleNotFoundError|ImportError): No module named ['\"]([^'\"]+)", output)
    if check.get("denied"):
        result.update(title="A check is waiting for permission", kind="approval", can_auto_fix=False,
                      what_happened="A command was declined, so that check could not run.",
                      meaning="Your files are saved. No passing result was assumed.",
                      next_step="Choose Resume task if you want to review the command again, or describe another way to test it.")
    elif "previous project folder" in output:
        result.update(title="A check still uses the old folder", kind="moved_project",
                      what_happened="The project was moved, but this check still names its previous location.",
                      meaning="Running that command could test the backup instead of your current project.",
                      next_step="Choose Try fixing it. SPARKLE CODER will inspect the check and use paths for the current project.")
    elif mismatch:
        expected, actual = mismatch.groups()
        result.update(title="The vocabulary count does not match the test", kind="expectation",
                      what_happened=f"The test expected {expected} text symbols, but the program counted {actual}.",
                      meaning="A vocabulary is the list of symbols the text reader knows. The test's expectation or the way that list is built may be wrong; the count alone cannot tell us which.",
                      next_step="Choose Try fixing it. SPARKLE CODER will inspect the text data and special symbols, then repair the code or correct its own test using evidence.")
    elif module:
        package = module.group(1)
        result.update(title="A required add-on is missing", kind="dependency",
                      what_happened=f"The project could not find {package} in the Python environment used for this check.",
                      meaning="The code cannot be fully tested until its required software is available.",
                      next_step="Choose Try fixing it. SPARKLE CODER will check the project setup and ask before running an installation command.")
    elif "PermissionError" in output or "Permission denied" in output:
        result.update(title="Your computer refused access", kind="permission", can_auto_fix=False,
                      what_happened="The app could not read, write, or run something it needed.",
                      meaning="This may be a folder permission or a file in use; the detailed error identifies it.",
                      next_step="Check that the project folder is writable and close any app holding the file, then resume.")
    elif check.get("cancelled"):
        result.update(title="The check was stopped", kind="stopped", can_auto_fix=False,
                      what_happened="The check ended before it could report a result.",
                      meaning="The work is saved, but this check is not complete.",
                      next_step="Resume the task when you want the remaining checks to run.")
    elif check.get("timed_out") or "exceeded its configured" in output:
        result.update(title="A check ran out of time", kind="timeout",
                      what_happened="The command reached its chosen time limit before finishing.",
                      meaning="This does not by itself mean the project is broken.",
                      next_step="Choose Try fixing it to inspect whether the command is stuck or needs more time.")
    elif "No tests were collected" in output or "Ran 0 tests" in output:
        result.update(title="The test command found no tests", kind="no_tests",
                      what_happened="The command ran, but it did not actually test any behavior.",
                      meaning="SPARKLE CODER needs to find the real tests or add a focused check.")
    elif "AssertionError" in output:
        result.update(title="The result differs from the test's expectation", kind="expectation",
                      what_happened="A test compared the expected result with the program's result, and they differed.",
                      meaning="The code or the test may need correcting. SPARKLE CODER should inspect both before changing either.")
    elif any(name in output for name in ("SyntaxError", "IndentationError", "NameError", "TypeError", "AttributeError")):
        result.update(title="The code encountered an error", kind="code",
                      what_happened="The program could not complete this check because part of the code needs attention.",
                      meaning="SPARKLE CODER can inspect the affected files and try a repair.")
    return result


def explain_checks(state):
    issues = []
    for check in active_checks(state):
        if check.get("ok"):
            continue
        item = explain_failure(check)
        duplicate = next((x for x in issues if (x["kind"], x["what_happened"], x["technical_details"])
                          == (item["kind"], item["what_happened"], item["technical_details"])), None)
        if duplicate:
            duplicate["check_ids"].extend(item["check_ids"])
        else:
            issues.append(item)
    if not issues:
        issues.append({"title": "The work still needs a check", "kind": "no_evidence", "can_auto_fix": True,
                       "what_happened": "The agent has not shown that the current project passes its checks.",
                       "meaning": "The files are saved. A completed message alone is not proof that the software works.",
                       "next_step": "Choose Try fixing it to find or add meaningful checks.",
                       "check_ids": [], "technical_details": ""})
    return issues


def simple_recovery(state, message="", action="checks"):
    if action == "checks":
        issue = explain_checks(state)[0]
        return {**issue, "message": issue["what_happened"], "action": action}
    if action == "connection" or any(x in message for x in ("Model API HTTP", "model endpoint", "connection attempts")):
        title = "The model connection needs attention"
        explanation = "SPARKLE CODER could not get a usable reply from the model service. Your project is saved."
        if "401" in message:
            explanation = "The model service did not accept the API key. Your project is saved."
        elif "429" in message:
            explanation = "The model service is temporarily limiting requests. Your project is saved."
        return {"title": title, "message": explanation, "what_happened": explanation,
                "meaning": "This is a connection issue, not proof of a problem in your project.",
                "next_step": "Open Connection settings, test the connection, then resume the saved task.",
                "technical_details": message, "action": "connection", "can_auto_fix": False}
    return {"title": "One detail is needed to continue", "message": message[:800],
            "what_happened": message[:800], "meaning": "Your work is saved.",
            "next_step": "Reply in the task box below, then choose Continue.", "technical_details": message,
            "action": action, "can_auto_fix": False}
