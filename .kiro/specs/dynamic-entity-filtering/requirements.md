# Dynamic Entity Filtering - Requirements

**Feature Name:** dynamic-entity-filtering  
**Status:** Draft  
**Created:** February 15, 2026  
**Priority:** HIGH - Critical user experience issue

---

## Problem Statement

When users query "show me how many items in our francis gays", the AI returns 20 items from ALL files instead of only the 7-16 items from the "francis gays" file. The semantic search is too broad and doesn't apply exact filtering when users specify entities like file names, project names, or categories.

**Current Behavior:**
- Query: "show me how many items in our francis gays?"
- Expected: 7-16 items (only from "francis gays" file)
- Actual: 20 items (from ALL files: francis gays, pedro cruz, john santos, maria reyes, etc.)

**Root Cause:**
- Semantic search treats "francis gays" as keywords, not as a file name filter
- No exact file_name filtering applied
- Router correctly detects Entity=FILE_NAME but UniversalHandler doesn't use this information

---

## User Stories

### 1. File Name Filtering
**As a** construction project manager  
**I want to** query items from a specific file by name  
**So that** I only see data from that file, not from all files

**Acceptance Criteria:**
- 1.1: When user queries "show me items in francis gays", system returns ONLY items from "francis gays" file
- 1.2: When user queries "how many items in pedro cruz", system returns ONLY items from "pedro cruz" file
- 1.3: File name detection works with patterns: "in [file]", "from [file]", "sa [file]", "ni [file]"
- 1.4: File name matching is case-insensitive
- 1.5: System uses vocabulary_loader to dynamically detect file names (no hardcoding)

### 2. Project Name Filtering
**As a** construction project manager  
**I want to** query items from a specific project  
**So that** I only see data from that project

**Acceptance Criteria:**
- 2.1: When user queries "show expenses in SJDM project", system returns ONLY items from SJDM project
- 2.2: When user queries "ilan ang items sa TEST project", system returns ONLY items from TEST project
- 2.3: Project name detection works with patterns: "in [project]", "sa [project]", "from [project]"
- 2.4: Project name matching is case-insensitive
- 2.5: System uses vocabulary_loader to dynamically detect project names

### 3. Category Filtering
**As a** construction project manager  
**I want to** query items by category  
**So that** I only see items in that category

**Acceptance Criteria:**
- 3.1: When user queries "show fuel expenses", system returns ONLY items with category="fuel"
- 3.2: When user queries "find food items", system returns ONLY items with category="food"
- 3.3: Category detection works with patterns: "[category] expenses", "[category] items", "category [category]"
- 3.4: Category matching is case-insensitive
- 3.5: System uses vocabulary_loader to dynamically detect categories

### 4. Combined Filtering
**As a** construction project manager  
**I want to** combine multiple filters in one query  
**So that** I can narrow down results precisely

**Acceptance Criteria:**
- 4.1: When user queries "show fuel expenses in francis gays", system filters by BOTH category AND file
- 4.2: When user queries "find food items in TEST project", system filters by BOTH category AND project
- 4.3: Multiple filters are applied with AND logic (all must match)
- 4.4: System handles 2-3 filters in a single query

### 5. Dynamic Vocabulary Loading
**As a** system  
**I want to** automatically detect new files, projects, and categories  
**So that** filtering works for user-created entities without code changes

**Acceptance Criteria:**
- 5.1: When user creates a new file, system automatically detects it in next query
- 5.2: When user creates a new project, system automatically detects it in next query
- 5.3: When user creates a new category, system automatically detects it in next query
- 5.4: Vocabulary is loaded from database on startup via vocabulary_loader
- 5.5: No hardcoded file/project/category names in code

### 6. Fallback to Semantic Search
**As a** user  
**I want** semantic search when no entity is specified  
**So that** I can still find items by keywords

**Acceptance Criteria:**
- 6.1: When user queries "find gcash" (no entity specified), system uses semantic search
- 6.2: When user queries "show transportation" (no entity specified), system uses semantic search
- 6.3: Semantic search returns results from ALL files/projects (current behavior)
- 6.4: System only applies exact filters when entity is explicitly mentioned

---

## Non-Functional Requirements

### Performance
- Entity detection must complete in <100ms
- Filtering must not slow down search (maintain <2s response time)
- Vocabulary loading on startup must complete in <5s

### Accuracy
- File name detection: >95% accuracy
- Project name detection: >95% accuracy
- Category detection: >90% accuracy
- False positive rate: <5% (don't filter when user didn't specify entity)

### Maintainability
- No hardcoded entity names in code
- All entity detection uses vocabulary_loader
- Easy to extend to new entity types (e.g., materials, quotations)

### Compatibility
- Must work with existing semantic search
- Must work with existing hybrid search
- Must not break current queries that don't specify entities

---

## Out of Scope

- Fuzzy matching for entity names (e.g., "francis gay" → "francis gays") - use typo corrector instead
- Entity disambiguation when multiple entities match (e.g., "francis" matches "francis gays" and "francis cruz")
- Natural language entity extraction (e.g., "the file I used yesterday") - requires conversation memory
- Entity aliases (e.g., "FG" → "francis gays") - future enhancement

---

## Success Metrics

### Accuracy Metrics
- File name queries return correct file: >95%
- Project name queries return correct project: >95%
- Category queries return correct category: >90%
- No false positives (filtering when not requested): >95%

### User Experience Metrics
- User satisfaction with search results: >90%
- Reduction in "wrong results" complaints: >80%
- Query refinement rate (user has to rephrase): <10%

### Performance Metrics
- Entity detection time: <100ms
- Total query response time: <2s
- Vocabulary loading time: <5s

---

## Dependencies

- vocabulary_loader.py (already exists - loads file/project/category names dynamically)
- router_service.py (already detects entity_type)
- semantic_extractor_v2.py (extracts search terms)
- universal_handler.py (needs modification to apply filters)

---

## Risks and Mitigations

### Risk 1: False Positives
**Risk:** System might filter when user didn't intend to (e.g., "show items" → filters by "items" as file name)  
**Mitigation:** Only filter when entity is explicitly mentioned with context patterns ("in [file]", "from [project]")

### Risk 2: Vocabulary Not Updated
**Risk:** User creates new file but system doesn't detect it until restart  
**Mitigation:** Implement vocabulary refresh mechanism (reload on demand or periodic refresh)

### Risk 3: Performance Degradation
**Risk:** Entity detection adds latency to every query  
**Mitigation:** Cache vocabulary in memory, use efficient string matching algorithms

### Risk 4: Breaking Existing Queries
**Risk:** New filtering logic breaks queries that currently work  
**Mitigation:** Extensive testing with existing query patterns, fallback to semantic search if no entity detected

---

## Testing Strategy

### Unit Tests
- Test entity extraction for file names
- Test entity extraction for project names
- Test entity extraction for categories
- Test filter application in UniversalHandler
- Test vocabulary loading

### Integration Tests
- Test end-to-end query with file name filter
- Test end-to-end query with project name filter
- Test end-to-end query with category filter
- Test combined filters
- Test fallback to semantic search

### User Acceptance Tests
- Test with real user queries from production logs
- Test with "francis gays" query (the original bug)
- Test with various file/project/category names
- Test with Tagalog and English queries

---

## Implementation Phases

### Phase 1: File Name Filtering (1-2 days)
- Implement entity extraction for file names
- Modify UniversalHandler to apply file_name filter
- Test with "francis gays" query

### Phase 2: Project Name Filtering (1 day)
- Implement entity extraction for project names
- Modify UniversalHandler to apply project_name filter
- Test with project-specific queries

### Phase 3: Category Filtering (1 day)
- Implement entity extraction for categories
- Modify UniversalHandler to apply category filter
- Test with category-specific queries

### Phase 4: Combined Filtering (1 day)
- Implement multi-filter support
- Test with combined filter queries
- Performance optimization

### Phase 5: Testing & Refinement (1-2 days)
- Comprehensive testing
- Bug fixes
- Performance tuning
- Documentation

**Total Estimated Time:** 5-7 days

---

## Related Documents

- FILE_NAME_FILTERING_ISSUE.md - Detailed analysis of the bug
- WHY_AI_RETURNS_DATA_THIS_WAY.md - Explanation of current behavior
- app/services/vocabulary_loader.py - Dynamic vocabulary loading
- app/services/router_service.py - Entity type detection
- app/services/query_handlers/universal_handler.py - Search implementation

---

## Approval

- [ ] Product Owner: _______________
- [ ] Tech Lead: _______________
- [ ] QA Lead: _______________

---

**Next Steps:**
1. Review and approve requirements
2. Create design document
3. Create implementation tasks
4. Begin Phase 1 implementation
