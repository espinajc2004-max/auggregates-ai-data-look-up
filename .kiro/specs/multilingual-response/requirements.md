# Multilingual Response Support - Requirements

## Feature Overview

Enable the AI chat system to respond in multiple languages (English and Filipino/Tagalog) based on user preference or automatic language detection.

**Current State**: 
- ✅ Input: NLP understands English, Filipino, and Taglish queries
- ❌ Output: Responses are hardcoded in Tagalog only

**Desired State**:
- ✅ Input: Continue supporting English, Filipino, and Taglish
- ✅ Output: Respond in English OR Filipino based on user's query language

---

## User Stories

### 1. Language Detection
**As a** user who asks questions in English  
**I want** the AI to respond in English  
**So that** I can understand the responses in my preferred language

**Acceptance Criteria**:
- 1.1 When user query contains primarily English words, AI responds in English
- 1.2 When user query contains primarily Filipino/Tagalog words, AI responds in Filipino
- 1.3 For mixed language (Taglish) queries, AI defaults to Filipino
- 1.4 Language detection accuracy should be > 85%

### 2. Consistent Message Translation
**As a** developer  
**I want** all response messages to have English and Filipino versions  
**So that** the system can respond in either language consistently

**Acceptance Criteria**:
- 2.1 All hardcoded Tagalog messages have English equivalents
- 2.2 Message templates support variable substitution (counts, names, etc.)
- 2.3 Both language versions convey the same meaning and information
- 2.4 Emojis and formatting are preserved across languages

### 3. Search Results Formatting
**As a** user  
**I want** search results formatted in my query language  
**So that** result headers, labels, and notes are readable

**Acceptance Criteria**:
- 3.1 Result count messages use detected language
- 3.2 Location labels ("Project", "File") use detected language
- 3.3 Disambiguation questions use detected language
- 3.4 Access restriction notes use detected language
- 3.5 Data values (amounts, names) remain unchanged regardless of language

### 4. Error and Help Messages
**As a** user  
**I want** error messages and help text in my query language  
**So that** I can understand what went wrong or what to do next

**Acceptance Criteria**:
- 4.1 Low confidence clarification messages use detected language
- 4.2 Access denied messages use detected language
- 4.3 No results messages use detected language
- 4.4 Help and greeting messages use detected language
- 4.5 Suggestion tips use detected language

### 5. Disambiguation Responses
**As a** user  
**I want** disambiguation questions in my query language  
**So that** I can understand my options clearly

**Acceptance Criteria**:
- 5.1 Multi-table disambiguation uses detected language
- 5.2 File selection prompts use detected language
- 5.3 Project selection prompts use detected language
- 5.4 Follow-up instructions use detected language

---

## Message Categories to Translate

### Category 1: Search Results (Priority: HIGH)
- "🔍 Nakakita ako ng **{count}** results sa {table}:"
- "🔍 Nahanap ko ang **'{value}'** sa {count} tables:"
- "📍 **{project}** → {file}"
- "... at {count} pang locations"

### Category 2: Disambiguation (Priority: HIGH)
- "❓ **Alin dito ang hinahanap mo?**"
- "Sabihin mo lang: 'yung sa Expenses' o 'yung sa CashFlow'"

### Category 3: Access Control (Priority: HIGH)
- "ℹ️ **Note:** May {count} pang results sa {tables} pero wala kang access."
- "Pasensya, wala kang access bilang {role} para dito."
- "Magtanong sa ADMIN o ACCOUNTANT para sa access."

### Category 4: No Results (Priority: MEDIUM)
- "❌ Walang nakitang results {context}."
- "💡 Tip: Subukan mo: 'fuel', 'car', 'Inflow', 'asda'"

### Category 5: Greetings & Help (Priority: MEDIUM)
- "Kumusta! 👋 Ako ang AI assistant mo para sa data lookup."
- "Pwede mo akong tanungin ng: ..."
- "Tanungin mo ako tungkol sa expenses, cashflow, projects, o quotations!"

### Category 6: Clarification (Priority: MEDIUM)
- "Hindi ko masyadong naintindihan. Pwede mo bang dagdagan ng detalye?"
- "Pasensya, hindi ko ito kayang sagutin."

### Category 7: Operation Results (Priority: LOW)
- "📊 May **{count}** na records {context}."
- "📋 Narito ang **{count}** records {context}."
- "📈 Ang total {context} ay **{count}** items."

---

## Technical Requirements

### TR-1: Language Detection Function
- Must detect language from user query text
- Should use keyword-based detection (fast, no external dependencies)
- Must return 'english' or 'filipino' as string
- Should handle edge cases (empty query, numbers only, etc.)

### TR-2: Message Dictionary Structure
- Must support nested message keys for organization
- Must support variable substitution using Python format strings
- Must be easily extensible for future languages
- Should be stored in a separate module (`app/utils/language.py`)

### TR-3: Response Builder Integration
- Must modify `_build_response_message()` to accept language parameter
- Must pass detected language through the call chain
- Must not break existing functionality
- Should maintain backward compatibility during transition

### TR-4: Performance
- Language detection must complete in < 5ms
- Message lookup must complete in < 1ms
- Total overhead must be < 10ms per request

---

## Implementation Approach

### Option 1: Automatic Language Detection (RECOMMENDED)
**Pros**: 
- Seamless user experience
- No API changes required
- Works immediately for all users

**Cons**:
- May misdetect language for very short queries
- No way to override if detection is wrong

### Option 2: User Preference Setting
**Pros**:
- 100% accurate language selection
- User has full control

**Cons**:
- Requires API changes (add language field to request)
- Requires frontend changes
- Users must explicitly set preference

### Option 3: Hybrid Approach
**Pros**:
- Best of both worlds
- Fallback to detection if no preference set

**Cons**:
- More complex implementation
- Requires both detection logic and preference storage

**DECISION**: Start with Option 1 (Automatic Detection), add Option 2 later if needed

---

## Out of Scope

- Translation of actual data values (amounts, names, categories)
- Support for languages other than English and Filipino
- User preference storage in database
- Frontend language selector UI
- Real-time language switching within a conversation

---

## Success Metrics

- **Language Detection Accuracy**: > 85% correct language detection
- **Response Time Impact**: < 10ms additional latency
- **Message Coverage**: 100% of user-facing messages translated
- **User Satisfaction**: Positive feedback from English-speaking users

---

## Dependencies

- None (pure Python implementation)
- No external libraries required
- No database schema changes required

---

## Risks and Mitigations

### Risk 1: Incorrect Language Detection
**Impact**: User receives response in wrong language  
**Mitigation**: Use conservative detection with clear keyword lists, default to Filipino for ambiguous cases

### Risk 2: Inconsistent Translations
**Impact**: Confusing or incorrect English messages  
**Mitigation**: Review all translations with native English speaker, maintain glossary

### Risk 3: Missing Message Translations
**Impact**: Some messages still in Tagalog even for English queries  
**Mitigation**: Comprehensive audit of all message strings, automated tests to verify coverage

---

## Testing Requirements

### Test Case 1: English Query Detection
- Input: "show me all expenses"
- Expected: Language detected as 'english'
- Expected: Response in English

### Test Case 2: Filipino Query Detection
- Input: "ipakita lahat ng expenses"
- Expected: Language detected as 'filipino'
- Expected: Response in Filipino

### Test Case 3: Taglish Query Detection
- Input: "show mo yung expenses"
- Expected: Language detected as 'filipino' (default for mixed)
- Expected: Response in Filipino

### Test Case 4: Search Results in English
- Input: "find fuel in cashflow"
- Expected: "🔍 I found **X** results in CashFlow:"

### Test Case 5: Search Results in Filipino
- Input: "hanapin fuel sa cashflow"
- Expected: "🔍 Nakakita ako ng **X** results sa CashFlow:"

### Test Case 6: Disambiguation in English
- Input: "search for gcash"
- Expected: "❓ **Which one are you looking for?**"

### Test Case 7: Access Denied in English
- Input: "show expenses" (as viewer role)
- Expected: "Sorry, you don't have access as viewer for this."

---

## Related Documentation

- `AI_RESPONSE_LANGUAGE.md` - Current analysis and implementation options
- `app/api/routes/chat.py` - Main chat endpoint with response building
- `WHY_SEARCH_CANNOT_UNDERSTAND_NLP.md` - NLP architecture overview

---

**Status**: Draft  
**Priority**: Medium  
**Estimated Effort**: 4-6 hours  
**Target Release**: Next sprint
