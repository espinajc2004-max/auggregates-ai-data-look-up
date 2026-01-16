# Project Name Filtering - Requirements

## Overview
The AI search system currently ignores project names specified in user queries. When a user asks "find gcash in Manila project", the system returns results from ALL projects instead of filtering to just Manila. This breaks the user's expectation and makes project-scoped searches impossible.

**IMPORTANT:** This solution must be **GENERIC and SCALABLE** - it must work for:
- ✅ ANY project in the database (not just test cases)
- ✅ NEW projects added in the future
- ✅ ANY project name format (full name, abbreviation, location)
- ✅ ANY data type (Expenses, CashFlow, Quotation, etc.)
- ✅ PRODUCTION use with real user queries

**Current Database State:**
- 5+ active projects (SJDM, Manila, Cebu, Davao, jzzy2's Project, etc.)
- 133+ indexed documents across all projects
- Multiple data types (Expenses, CashFlow, Quotation, QuotationItem)
- Projects with different naming patterns and locations

## Problem Statement
**Current Behavior:**
- User query: "hanapin gcash sa Manila project"
- Expected: Results from Manila project only
- Actual: Results from SJDM, Manila, AND Cebu projects (all projects)

**Root Cause:**
1. Entity matcher extracts project name correctly ("Manila")
2. BUT stores it as `filters["project"]` (project name string)
3. Universal handler expects `filters["project_id"]` (UUID)
4. No conversion happens between project name → project_id
5. Database function receives `p_project_id = NULL`
6. NULL means "search all projects"

## User Stories

### 1. Project-Scoped Search
**As a** construction project manager  
**I want to** search for data within a specific project  
**So that** I only see relevant results for that project

**Acceptance Criteria:**
- 1.1 When user specifies project name in query, system filters to that project only
- 1.2 System handles various project name formats (full name, abbreviation, location)
- 1.3 System returns results ONLY from the specified project
- 1.4 System shows clear indication of which project was searched

**Examples:**
```
Query: "hanapin gcash sa Manila project"
Expected: Results from "MANILA CONSTRUCTION PROJECT" only

Query: "find fuel in SJDM"
Expected: Results from "SJDM BULACAN PROJECT" only

Query: "search worker salary sa Cebu Warehouse"
Expected: Results from "CEBU WAREHOUSE PROJECT" only
```

### 2. Project Name Resolution
**As a** system  
**I want to** convert project names to project IDs  
**So that** I can filter database queries correctly

**Acceptance Criteria:**
- 2.1 System resolves full project names to UUIDs
- 2.2 System resolves abbreviations (SJDM, Manila, Cebu) to UUIDs
- 2.3 System resolves location names (San Jose, Bulacan) to UUIDs
- 2.4 System handles case-insensitive matching
- 2.5 System handles partial matches (e.g., "Manila" matches "MANILA CONSTRUCTION PROJECT")

**Examples:**
```
Input: "Manila" → Output: UUID of "MANILA CONSTRUCTION PROJECT"
Input: "SJDM" → Output: UUID of "SJDM BULACAN PROJECT"
Input: "san jose" → Output: UUID of "SJDM BULACAN PROJECT"
Input: "Cebu Warehouse" → Output: UUID of "CEBU WAREHOUSE PROJECT"
```

### 3. Multi-Project Search (Default)
**As a** user  
**I want to** search across all projects when I don't specify one  
**So that** I can find data regardless of project

**Acceptance Criteria:**
- 3.1 When no project is specified, system searches all projects
- 3.2 Results show project name for each item
- 3.3 Results are sorted by relevance across all projects

**Examples:**
```
Query: "hanapin gcash"
Expected: Results from ALL projects (SJDM, Manila, Cebu, Davao)

Query: "find fuel"
Expected: Results from ALL projects
```

### 4. Project Clarification
**As a** user  
**I want to** be asked which project when my query is ambiguous  
**So that** I get the right results

**Acceptance Criteria:**
- 4.1 System asks for project when search term is vague (< 4 chars, no numbers)
- 4.2 System provides list of available projects
- 4.3 System accepts project selection in follow-up query

**Examples:**
```
Query: "find car"
Response: "Hanapin 'car' sa aling project?
  1. SJDM BULACAN PROJECT
  2. MANILA CONSTRUCTION PROJECT
  3. CEBU WAREHOUSE PROJECT
  4. DAVAO RESIDENTIAL PROJECT"

Follow-up: "sa Manila"
Response: [Results from Manila project only]
```

## Technical Requirements

### 1. Project Name to ID Conversion (GENERIC SOLUTION)
**Must work for ANY project, not just test cases:**
- Query Project table dynamically to get UUID from ANY project name
- Handle fuzzy matching for typos, abbreviations, partial names
- Support multiple name formats:
  - Full name: "MANILA CONSTRUCTION PROJECT"
  - Abbreviation: "Manila", "SJDM", "Cebu"
  - Location: "San Jose", "Bulacan", "Manila City"
  - Partial: "Manila", "Cebu Warehouse", "Davao Residential"
- Cache project mappings for performance (invalidate on project changes)
- Handle case-insensitive matching
- **NO HARDCODED PROJECT NAMES** - all lookups must be database-driven

### 2. Filter Pipeline Enhancement (SCALABLE ARCHITECTURE)
**Pipeline flow:**
1. User query → Entity matcher extracts project name → stores as `filters["project"]`
2. **NEW:** Project resolver service:
   - Takes `filters["project"]` (string name)
   - Queries database: `SELECT id FROM Project WHERE project_name ILIKE '%{name}%'`
   - Returns `filters["project_id"]` (UUID)
   - Handles fuzzy matching and abbreviations
3. Universal handler uses `filters["project_id"]` in database query
4. Database function filters by `p_project_id`

**Key Design Principles:**
- Database-driven (no hardcoded values)
- Fuzzy matching (handles typos and variations)
- Caching (performance optimization)
- Extensible (works with future projects)

### 3. Performance Considerations
- Project name resolution should be fast (< 50ms)
- Cache project name → ID mappings in memory
- Cache invalidation on project CRUD operations
- Should not add significant latency to queries
- Batch project lookups when possible

### 4. Error Handling (PRODUCTION-READY)
- If project name not found → return helpful error with suggestions
- If multiple projects match → ask for clarification with options
- If project name is ambiguous → suggest alternatives
- Handle edge cases:
  - Empty project name
  - Special characters in project name
  - Very long project names
  - Projects with similar names

## Success Criteria

### Functional Success
- ✅ 90%+ of project-scoped queries return correct results
- ✅ Project filtering works for all query types (search, count, list)
- ✅ System handles abbreviations and variations correctly
- ✅ Multi-project search still works when no project specified

### Performance Success
- ✅ Project name resolution adds < 50ms latency
- ✅ No degradation in search performance
- ✅ Caching reduces repeated lookups

### User Experience Success
- ✅ Users can specify projects naturally in queries
- ✅ Clear feedback when project is filtered
- ✅ Helpful error messages when project not found

## Out of Scope
- Conversation context (remembering last project)
- Multi-project comparison queries
- Project hierarchy (parent/child projects)
- Project permissions (all users see all projects)

## Dependencies
- Supabase Project table with UUID primary keys
- Entity matcher for project name extraction
- Universal handler for search execution
- Database function `ai_search_universal_v2` with project_id parameter

## Risks and Mitigations

### Risk 1: Project Name Ambiguity
**Risk:** Multiple projects with similar names  
**Mitigation:** Use fuzzy matching with confidence threshold, ask for clarification if ambiguous

### Risk 2: Performance Impact
**Risk:** Project name lookup adds latency  
**Mitigation:** Cache project mappings, use indexed queries

### Risk 3: Backward Compatibility
**Risk:** Breaking existing queries that don't specify project  
**Mitigation:** Make project filtering optional (NULL = all projects)

## Testing Strategy

### Unit Tests
- Test project name to ID conversion with REAL database projects
- Test fuzzy matching logic with various inputs
- Test cache behavior (hit/miss/invalidation)
- Test error handling for edge cases
- **Test with projects NOT in test cases** (verify generic solution)

### Integration Tests
- Test end-to-end project-scoped search with ALL projects
- Test multi-project search (no project specified)
- Test project clarification flow
- Test various project name formats (full, abbreviation, location)
- **Test with NEW projects added after implementation**

### Acceptance Tests
- Run `project_scoped_test.py` - expect 90%+ success rate
- Test with real user queries from production
- Test with abbreviations and variations
- Test performance under load
- **Add new project to database and verify filtering works immediately**

### Scalability Tests
- Add 10 new projects → verify filtering works
- Test with 100+ projects → verify performance
- Test with projects having similar names → verify disambiguation
- Test with special characters in project names

## Acceptance Criteria Summary

**This feature is complete when:**
1. ✅ Project-scoped queries return results from specified project only
2. ✅ System handles project name variations (full name, abbreviation, location)
3. ✅ Multi-project search works when no project specified
4. ✅ Project name resolution is fast (< 50ms)
5. ✅ `project_scoped_test.py` shows 90%+ success rate
6. ✅ No regression in existing search functionality

## Priority
**HIGH** - This is a critical feature for production use. Users need to be able to search within specific projects.

## Estimated Effort
- Design: 1 hour (DONE - this document)
- Implementation: 2-3 hours
- Testing: 1 hour
- Total: 4-5 hours
