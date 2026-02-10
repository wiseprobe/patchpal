# PatchPal Documentation

This directory contains the source files for PatchPal's documentation site, built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

## Building the Documentation

1. **Install dependencies:**
   ```bash
   pip install -e ".[docs]"
   ```

2. **Build the site:**
   ```bash
   mkdocs build
   ```

3. **Serve locally for development:**
   ```bash
   mkdocs serve
   ```
   Then visit http://127.0.0.1:8000

## Documentation Structure

- `index.md` - Homepage
- `getting-started/` - Installation and setup guides
- `features/` - Feature documentation (tools, skills, custom tools)
- `models/` - Model configuration
- `usage/` - Usage guides (interactive, Python API, autopilot)
- `configuration.md` - Environment variables
- `safety.md` - Security model
- `context-management.md` - Context window management
- `troubleshooting.md` - Common issues and solutions

## Deployment

The documentation is automatically deployed to GitHub Pages when changes are pushed to the main branch.

## Contributing

When adding new pages:
1. Create the markdown file in the appropriate directory
2. Add it to `nav` section in `mkdocs.yml`
3. Test locally with `mkdocs serve`
4. Build with `mkdocs build` to verify no warnings/errors
