# Tag Support Contributor Checklist

Use this checklist for each new support note entry.

## 1. Scope

- Confirm engine and capability (for this set: routing).
- Use router_with_profiles in each engine YAML (one engine file containing profiles[]).
- Confirm profile or costing mode (for example car, bicycle, foot, trekking).
- Confirm tag keys covered (surface, smoothness, tracktype).

## 2. Evidence Quality

- Add at least one primary source reference from upstream code or profile.
- Prefer parser or handler code over tests or comments when possible.
- Record exact file and line where behavior is implemented.
- Set confidence level (high, medium, low).

## 3. Behavior Extraction

- Record support_level (direct, derived, profile_dependent, user_defined_only).
- Record effect_types (speed_cap, speed_factor, priority_factor, access_block, route_preference, inferred_fallback).
- Record precedence order when multiple tags interact.
- Capture unknown_value_behavior and missing_tag_behavior.
- Capture hard exclusions (for example impassable).

## 4. Value Rules

- Add concrete value_rules for common values.
- Include conditions if branch-dependent (profile flags, options, mode).
- If values are context-dependent, say so explicitly instead of guessing a single value.

## 5. Special Handling

- Note derived or merged fields (for example integrity indices, encoded values).
- Note fallback heuristics when tags are missing.
- Note whether behavior is profile-specific or global.

## 6. Verification

- Set verified_on date in ISO format (YYYY-MM-DD).
- Re-check at least one evidence pointer before merge.
- If behavior is uncertain, lower confidence and add a follow-up note.

## 7. Consistency Checks

- Keep entry structure aligned with docs/tag-support-schema.yaml.
- Use consistent terminology across engines.
- Avoid status claims without evidence.
