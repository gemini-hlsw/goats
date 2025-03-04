# `towncrier` for Change Logs

In our project, we use `towncrier` to generate change logs for each release. Change logs are constructed from small, individual files known as *news fragments*. These files briefly document the changes made.

## Creating News Fragments

News fragments are succinct files that describe a change in the project. They are written in markdown (`.md`).

When writing news fragments, remember to keep them concise and reader-oriented.
  - Group related fragments: Use the ID of ticket to create a news fragment, and update it as necessary.
  - Prioritize user impact: Bug fixes and minor improvements to the code that were not previously released do not require news fragments, however, if in development prior to release, documenting these changes are fine.
  - Start with a descriptive title: This helps readers quickly understand the purpose of the update. Jira ticket title is often a good summary of the change or feature being introduced.
  - Use active voice and past tense: For example, use words like "added," "improved," "fixed," "enhanced," or "optimized" to convey the action taken.
  - Keep it brief and focused: News fragments should be concise and to the point. Focus on the most important details of the change and omit technical details.
  - Provide links or references: If applicable, provide references to relevant documents.
  - Proofread and review: Ensure that the news fragments are free from errors and are easy to understand.

Here are the steps to create a news fragment:

1. Name your file using the following pattern: `<GOATS-N>.<TYPE>.md`.
  - Replace `<GOATS-N>` with the ID of the corresponding ticket on our JIRA board
    - For instance, `GOATS-22`.
  - Substitute `<TYPE>` with one of the following change types:
    - `new`: for introducing new features.
    - `bugfix`: for fixing bugs.
    - `change`: for changes to the behavior in released code.
    - `perf`: for performance enhancement changes.
    - `other`: for all other changes or additions (tests, docs, infrastructure).
  - For instance, a correctly named file might look like `GOATS-22.other.md`.

2. Save the file to `doc/changes`.

## Previewing Changes

Before finalizing the change log, you can preview how your contributions will appear in it:

1. Ensure `towncrier` is installed. If not, you can install it via `pip` or `conda-forge`.

2. In your terminal, execute `towncrier build --draft`. This will create a draft of the release notes incorporating your changes without altering the final document.

## Building the Change Log

Once you're ready to finalize the change log:

1. Execute `towncrier build` in your terminal. This command will create or update the `CHANGES.md` file.

   - If the change log has already been updated for the same version, you will encounter a `ValueError` message indicating that newsfiles for this version already exist.

2. To specify a version, append the `--version` flag followed by the version number, like so: `towncrier build --version 1.0.0`.

Maintaining clear and concise notes will make it easier for users to understand the changes introduced in each release.