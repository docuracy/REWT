# The gems GitHub Pages itself uses, pinned as one set.
#
# AT THE REPOSITORY ROOT, NOT IN docs/, AND THAT IS THE POINT. `bundler-cache` installs
# into `vendor/bundle` beside the Gemfile; with the Gemfile in docs/ that puts a few
# hundred gems INSIDE THE SITE SOURCE, and Jekyll then tries to build them — the run
# died on a date placeholder in Jekyll's own new-site template,
# `0000-00-00-welcome-to-jekyll.markdown.erb`.
#
# The usual remedy is to add `vendor` to `exclude:` in _config.yml. Keeping the
# Gemfile out here is better: the site source stays content only, nothing about the
# build leaks into a file that describes the site, and docs/_config.yml does not have
# to know that a bundler exists.
#
# The site builds from a workflow now rather than from the branch, and the workflow
# has to reproduce what GitHub's own builder did — including the themes it bundles.
# Installing bare Jekyll does not: `_config.yml` asks for `jekyll-theme-primer` and
# the build died on `Could not find 'jekyll-theme-primer'`.
#
# The `github-pages` gem is that reproduction. It pins Jekyll, every supported theme
# and every allowed plugin to the exact versions Pages runs, so the workflow builds
# what the branch build built rather than something close to it. Naming Jekyll's
# version here instead would drift from Pages the first time either moved.
source "https://rubygems.org"
gem "github-pages", group: :jekyll_plugins
