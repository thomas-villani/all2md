- **Chunks packed to `max_tokens` no longer overshoot it.** With tiktoken, the `semantic`
  (token) and `sentence` strategies could emit a chunk one token over the limit ("Chunk 62
  exceeds max_tokens (257 > 256)"), which was then re-split by character, cutting a word
  and leaving a fragment chunk behind. The sentence, paragraph, line and section chunkers
  now check the real count of each candidate span (separators included) rather than a sum
  of each unit's own count, and the token chunker shrinks a window whose re-sliced text
  counts over the limit (#686).
