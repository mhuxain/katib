# Coding guidance

Keep code simple. Do the requested change, nothing more.

- No premature abstractions. Three similar lines is fine — abstract on the third repeat, not the first.
- No speculative features, options, or config for hypothetical future needs.
- No error handling for cases that cannot happen. Validate at system boundaries only.
- No backwards-compatibility shims for code that has no other callers.
- Default to no comments. Add one only when the *why* is non-obvious.
- Prefer editing existing files over creating new ones.
