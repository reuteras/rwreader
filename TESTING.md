# RWReader Testing Guide

This document provides comprehensive test scenarios for manually testing rwreader functionality.

## Running in Debug Mode

To get detailed logs for debugging:

```bash
# Run with debug logging
rwreader --debug

# View logs in real-time
tail -f ~/.rwreader/logs/rwreader.log

# Or run with info level
rwreader --info
```

## Test Scenarios

### 1. Category List Tests

#### 1.1 Initial Load
- **Steps**: Launch rwreader
- **Expected**:
  - Categories display with counts: Inbox, Later, Feed, Archive
  - Counts are accurate (match web interface)
  - No errors in logs

#### 1.2 Category Refresh (Issue #28, #30, PR #29, #31)
- **Steps**:
  1. Launch app
  2. Note current counts
  3. Press 'r' to refresh
  4. Repeat 'r' multiple times rapidly
- **Expected**:
  - List clears immediately when 'r' is pressed (visual feedback)
  - "Refreshing categories..." notification shows
  - Categories reload with updated counts
  - No "duplicate widget ID" errors
  - No crashes on multiple rapid refreshes
  - Logs show: "action_refresh called", "load_categories called with refresh=True"

#### 1.3 Category Navigation
- **Steps**:
  1. Use 'j'/'k' or arrow keys to move between categories
  2. Press Enter on each category
- **Expected**:
  - Cursor moves correctly
  - Pressing Enter opens the selected category's article list

### 2. Article List Tests

#### 2.1 Initial Article Load
- **Steps**:
  1. Select a category (Inbox, Feed, Later, or Archive)
  2. Wait for articles to load
- **Expected**:
  - Articles display with titles
  - Loading notification appears
  - Success notification shows count
  - Articles match web interface
  - No duplicate IDs in logs

#### 2.2 Article List Refresh
- **Steps**:
  1. Open a category
  2. Press 'r' to refresh
  3. Repeat multiple times
- **Expected**:
  - Articles reload from API
  - Counts update if changed
  - No crashes
  - No duplicate ID errors

#### 2.3 Article Navigation
- **Steps**: Use 'j'/'k' to move through article list
- **Expected**:
  - Cursor moves correctly
  - Read/unread status visually distinct (bold for unread)

### 3. Article Reader Tests

#### 3.1 Open Article
- **Steps**:
  1. In article list, select an article
  2. Press Enter
- **Expected**:
  - Article content displays
  - Title, author, metadata shown
  - Content is readable and formatted

#### 3.2 Article Navigation (J/K)
- **Steps**:
  1. Open an article
  2. Press 'J' for next article
  3. Press 'K' for previous article
- **Expected**:
  - Articles switch correctly
  - No crashes at list boundaries
  - Content updates properly

### 4. Article Actions Tests

#### 4.1 Archive Article from Reader (Issue #34)
- **Steps**:
  1. Open Inbox article
  2. Press 'a' to archive
  3. Press ESC to return to list
  4. **Check**: Is archived article still in list?
  5. Press 'r' to refresh
  6. **Check**: Does refresh work without crash?
- **Expected**:
  - Success notification shows
  - **After ESC**: Article should NOT appear in list (Issue #34 fix)
  - Refresh should work without crash
  - Logs show: "ArticleListScreen resumed, refreshing articles"

#### 4.2 Move Article to Later from Reader
- **Steps**:
  1. Open Inbox article
  2. Press 'l' to move to Later
  3. Return to list
- **Expected**:
  - Article removed from Inbox
  - Article appears in Later category
  - List updates correctly on return

#### 4.3 Move Article to Inbox from Reader
- **Steps**:
  1. Open Later/Archive article
  2. Press 'i' to move to Inbox
  3. Return to list
- **Expected**:
  - Article removed from current category
  - Article appears in Inbox
  - List updates on return

#### 4.4 Delete Article from Reader (Issue #32, PR #33)
- **Steps**:
  1. Open an article
  2. Press 'D' (capital D)
  3. Confirm deletion
- **Expected**:
  - Confirmation dialog appears (no NoActiveWorker error)
  - After confirmation: article deleted
  - Next article loads or returns to list if none
  - Success notification shows
  - List updates on return

#### 4.5 Delete Article from List (Issue #32, PR #33)
- **Steps**:
  1. In article list, highlight an article
  2. Press 'D'
  3. Confirm deletion
- **Expected**:
  - Confirmation dialog appears (no NoActiveWorker error)
  - After confirmation: article removed from list
  - List updates immediately

### 5. Browser Integration Tests

#### 5.1 Open Article in Browser
- **Steps**:
  1. Open article or highlight in list
  2. Press 'o'
- **Expected**:
  - Default browser opens with article URL
  - Notification shows
  - App remains functional

#### 5.2 Link Extraction (Ctrl+L)
- **Steps**:
  1. Open article with links
  2. Press Ctrl+L
  3. Select a link
  4. Press 'o' to open
- **Expected**:
  - Links list appears
  - Browser opens selected link
  - Can navigate with j/k

### 6. Theme and UI Tests

#### 6.1 Dark Mode Toggle
- **Steps**: Press 'd' to toggle dark mode
- **Expected**:
  - Theme switches between light and dark
  - All UI elements readable
  - No visual glitches

#### 6.2 Help Screen
- **Steps**: Press 'h' or '?'
- **Expected**:
  - Help screen shows all keybindings
  - ESC returns to previous screen

### 7. Edge Cases and Error Handling

#### 7.1 Empty Category
- **Steps**: Open a category with no articles
- **Expected**:
  - Graceful message
  - No crashes
  - Can navigate away

#### 7.2 Network Error
- **Steps**:
  1. Disconnect network
  2. Try to refresh
- **Expected**:
  - Error notification
  - App remains functional
  - Can retry when network returns

#### 7.3 Rapid Key Presses
- **Steps**: Rapidly press various keys (j, k, r, ESC, etc.)
- **Expected**:
  - No crashes
  - Actions queue properly or are ignored
  - UI remains responsive

#### 7.4 Last Article in List
- **Steps**:
  1. Move to last article in a list
  2. Archive/delete it
  3. Try to navigate
- **Expected**:
  - Returns to list or loads previous article
  - No index errors
  - Graceful handling

### 8. Workflow Integration Tests

#### 8.1 Complete Article Workflow
- **Steps**:
  1. Start in Inbox
  2. Read article
  3. Archive it
  4. Return to list
  5. Verify it's gone
  6. Check Archive category
- **Expected**: Article flow is seamless

#### 8.2 Batch Processing
- **Steps**:
  1. Open Inbox
  2. Archive multiple articles using 'a', 'J' pattern
  3. Return to list
- **Expected**: All archived articles removed from list

## Known Issues

### Fixed
- ✅ Issue #24: Duplicate widget IDs on refresh (Fixed in PR #25, #31)
- ✅ Issue #26: Refresh not fetching from API (Fixed in PR #27)
- ✅ Issue #28: Category refresh improvements (Fixed in PR #29)
- ✅ Issue #30: Duplicate IDs from explicit widget IDs (Fixed in PR #31)
- ✅ Issue #32: Delete action NoActiveWorker error (Fixed in PR #33)

### In Progress
- 🔧 Issue #34: Article list not updating after archive + refresh crash

## Reporting Issues

When reporting issues, please include:

1. **Steps to Reproduce**: Exact sequence of actions
2. **Expected Behavior**: What should happen
3. **Actual Behavior**: What actually happened
4. **Logs**: Relevant entries from `~/.rwreader/logs/rwreader.log`
5. **Environment**: OS, Python version, rwreader version
6. **Screenshots**: If applicable

## Debug Log Analysis

Key log patterns to look for:

```
# Category refresh
action_refresh called
Clearing X items from view
Clearing client cache
load_categories called with refresh=True
Fetching inbox data...
Got X inbox items

# Article list resume
ArticleListScreen resumed, refreshing articles
load_articles called with load_more=False

# Errors to watch for
DuplicateIds: Tried to insert a widget with ID
NoActiveWorker: push_screen must be run from a worker
Error loading categories/articles
```

## Performance Testing

### Response Times
- Category load: Should be < 2 seconds
- Article list load: Should be < 3 seconds
- Article open: Should be < 1 second (if cached)
- Refresh: Should complete in < 5 seconds

### Memory Usage
- Monitor for memory leaks during extended use
- Check logs for excessive cache growth

## Automated Testing

Currently, rwreader uses manual testing. Future improvements:
- Unit tests for client methods
- Integration tests for UI flows
- Regression test suite
- CI/CD pipeline with automated checks
