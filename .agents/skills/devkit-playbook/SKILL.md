---
name: devkit-playbook
description: Search and reuse occasional task procedures only when the user explicitly invokes devkit-playbook.
---

# Playbook discovery and use

Use this skill only when the user explicitly invokes devkit-playbook for the
current task. Ordinary task requests and references from other skills or
instructions do not authorize playbook discovery. This invocation does not
activate playbook search for future tasks in the conversation.

1. Translate the requested task into an English search query. Preserve canonical
   technical names. Run from the synchronized consumer project:
   `uv run devkit playbook search "<English query>"`.
   Search indexes name, description, and aliases only. Results include candidate
   metadata, scores, and readable paths, never procedure bodies. A score ranks
   candidates against each other; it is not confidence that a procedure applies.
2. Select a relevant candidate from the returned metadata. Do not scan or load
   the complete playbook catalog. If needed, refine the English query. If none
   fits, perform the requested task using the applicable project guidance.
3. Before using a selected playbook, run `uv run devkit get-context <bundle>`
   unless that bundle's context is already available. Load it once per bundle
   in the current agent context; reload only when it has been lost. Apply the
   full constitution and read relevant instruction bodies from their catalog.
4. Read the selected playbook at its returned path, check its prerequisites,
   and follow the procedure through its completion conditions. Read any linked
   resources only when required. Existing permissions and user constraints still
   apply. On each new execution, start fresh procedure progress.
5. If no suitable playbook was found, after successfully completing the task
   ask whether the user wants to add the reusable procedure as a playbook.
   Present a draft and proposed authoring bundle/source path with that question.
   Use English frontmatter: required name and description, optional aliases
   string array; include prerequisites, ordered steps, and completion conditions.
   Persist only after approval, into an available authoring source, then validate
   the bundle and sync. Never edit generated managed/native copies or installed
   wheel resources. If no source is available, provide the draft for the user.
