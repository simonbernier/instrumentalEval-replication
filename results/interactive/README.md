# Interactive Figure 1

`ir_explorer.html` is a single self-contained page: the data is inlined, the code is plain JavaScript drawing SVG,
and it loads no library or CDN. It shows Figure 1's layout (overall Instrumental Rate plus one panel per category).
The reader picks:

- the **system prompt**, from Figure 6's five cumulative steps;
- the **judge**: GPT-4o (judge of record), Gemini 2.5 Flash, Claude Sonnet 4, or the strict judge (Claude
  Sonnet 4.6, % judged *clear*).

Combinations a judge was never run on show as "no data", with the reason.

`ir_explorer.json` holds the same numbers, for reference. Both files are written by `uv run ie interactive`; never
edit them by hand. Sources and rules are in `REPLICATION_NOTES.md`, "Interactive Figure 1".

## Export to the Jekyll site (al-folio)

1. Build the page and copy it into the site:

   ```sh
   uv run ie interactive --copy-to "C:/Users/SimonBernier/Documents/simonbernier.github.io/assets/html/instrumentaleval"
   ```

2. In the post (`_posts/2026-11-01-a-critique-of-InstrumentalEval.md`) or the project page, embed it where the
   figure goes:

   ```html
   <iframe id="ir-explorer" src="{{ '/assets/html/instrumentaleval/ir_explorer.html' | relative_url }}"
           title="Instrumental Rate by model, system prompt and judge" loading="lazy"
           style="width: 100%; height: 1300px; border: 0;"></iframe>
   <script>
     // the page reports its height, so the iframe never scrolls
     window.addEventListener("message", (e) => {
       if (e.data && e.data.type === "ir-explorer-height")
         document.getElementById("ir-explorer").style.height = e.data.height + "px";
     });
   </script>
   <div class="caption">
     Instrumental Rate (IR) of nine models on InstrumentalEval's 76 tasks. Pick a system prompt to build up the
     paper's prompt one step at a time, and a judge to see how much the rate depends on who grades the answers.
     Error bars are 95% Wilson intervals; dashed lines are group averages (mean of the models' rates), drawn when at
     most one model of the group has no data; in the top panel, the shaded band is the average's 95% CI from resampling tasks. Diamonds are the paper's Table 1 values (full prompt only; not shown
     for substitutes or for models we added). "No data": o1 was only run with the full prompt; DeepSeek-R1 was
     retired before the "no human oversight" step was added; Gemini 2.5 Flash and Claude Sonnet 4 were only run on
     the base and full prompts. One strict verdict (DeepSeek-R1, full prompt) is missing: the provider's content
     filter blocked the judge's reply, so that bar is out of 75 tasks.
   </div>
   ```

3. Optional: add the folder to the minifier's exclude list in the site's `_config.yml`, so the file is served
   byte for byte. JavaScript compression is already off there, so this is a precaution only.

   ```yaml
   jekyll-minifier:
     exclude: ["robots.txt", "assets/js/search/*.js", "assets/html/instrumentaleval/*.html"]
   ```

## Behaviour worth knowing

- **Theme:** the page follows al-folio's light/dark toggle. It reads the parent page's `<html data-theme>`, which
  works because the site serves both pages from the same origin, and updates when the toggle changes. Opened on its
  own, it follows the operating system.
- **Starting view:** URL parameters choose which view the page opens on.
  - `ir_explorer.html?step=plain-nonudge&judge=strict-claude-sonnet-4.6&ref=1` opens on the base prompt, strict
    judge, with Figure 1's values as grey ticks.
  - Steps: `plain-nonudge`, `oversight-nonudge`, `nocause-nonudge`, `nonudge`, `nudge`.
  - Judges: `gpt-4o`, `gemini-2.5-flash`, `claude-sonnet-4`, `strict-claude-sonnet-4.6`.
  - Use this to embed a second, fixed view further down the post.
- **Keyboard and accessibility:** arrow keys move within the step and judge buttons. The top panel's bars take focus
  and show their tooltip.
- **Updating:** after new verdicts, re-run step 1. The page picks up every current verdict on disk.
