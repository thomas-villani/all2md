- **CSV exports keep values in their columns after a merged cell spans rows.**
  Header and body rowspans now use the shared table layout, including effective
  spans when merges collide. The existing `repeat`, `blank` and `placeholder`
  modes apply to every covered position. Ordinary ragged rows and colspan-only
  output keep their existing lengths and values.
