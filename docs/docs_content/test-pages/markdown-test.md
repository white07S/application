---
sidebar_position: 1
title: Markdown Test
description: Testing markdown rendering capabilities
---

# Markdown Rendering Test

This page demonstrates various markdown features supported by NFR Connect documentation.

## Text Formatting

**Bold text** and *italic text* and ***bold italic text***.

~~Strikethrough text~~ and `inline code`.

> This is a blockquote. It can span multiple lines and contains important information that should stand out from the rest of the content.

## Lists

### Unordered List

- First item
- Second item
  - Nested item A
  - Nested item B
- Third item

### Ordered List

1. First step
2. Second step
   1. Sub-step 2.1
   2. Sub-step 2.2
3. Third step

### Task List

- [x] Completed task
- [x] Another completed task
- [ ] Pending task
- [ ] Future task

## Links and Images

[External link to Google](https://google.com)

[Internal link to Introduction](/getting-started/introduction)

## Tables

| Header 1 | Header 2 | Header 3 |
|----------|:--------:|---------:|
| Left | Center | Right |
| aligned | aligned | aligned |
| Cell 1 | Cell 2 | Cell 3 |

## Admonitions

<Note title="This is a **note** admonition. Use it for general information.">

</Note>

<Tip title="This is a **tip** admonition. Use it for helpful suggestions.">

</Tip>

<Info title="This is an **info** admonition. Use it for important context.">

</Info>

<Warning title="This is a **warning** admonition. Use it for potential issues.">

</Warning>

<Danger title="This is a **danger** admonition. Use it for critical warnings.">

</Danger>

## Details/Collapsible

<details>
<summary>Click to expand</summary>

This content is hidden by default. It can contain any markdown content including:

- Lists
- Code blocks
- Tables

```javascript
console.log('Hidden code!');
```

</details>

## Horizontal Rule

---

## Footnotes

Here's a sentence with a footnote[^1].

[^1]: This is the footnote content.

## Definition Lists

Term 1
: Definition for term 1

Term 2
: Definition for term 2
: Another definition for term 2
