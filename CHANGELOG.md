# Changelog - Code Review Fixes

## [Unreleased] - 2025-10-02

### 🔒 Security Fixes

#### Critical
- **[SECURITY]** Removed hardcoded Flask secret key, now uses environment variable `FLASK_SECRET_KEY`
- **[SECURITY]** Moved Gemini API key to environment variable `GEMINI_API_KEY` 
- **[SECURITY]** Fixed SQL injection risk by replacing raw SQL with SQLAlchemy ORM queries
- **[SECURITY]** Added `.env` to `.gitignore` to prevent credential leaks

#### Added
- Created `.env.template` for easy environment setup
- Created `SECURITY.md` with security guidelines
- Created automated `setup.sh` script

### 🐛 Bug Fixes

#### Critical
- Fixed database connection context bug - replaced non-existent `db.get_connection()` with proper `db.get_session()`
- Fixed 5 instances of bare `except:` clauses that could hide critical errors
- All exceptions now properly logged with context

#### High Priority
- Fixed ImportError handling in `usb_json_reader.py` (was catching all exceptions)
- Fixed scheduler shutdown hanging on exit (added `wait=False`)
- Added SSE queue size limit (1000) to prevent memory leaks

### ♻️ Code Quality Improvements

- Replaced magic number `10000` with named constant `MAX_READINGS_BEFORE_ROLLOVER`
- Improved error messages with actionable context
- Added proper session cleanup in all database operations
- Better logging with structured error messages

### 📝 Configuration Changes

- **[BREAKING]** Logging now properly respects `LOG_LEVEL` environment variable
  - Development: Set `LOG_LEVEL=DEBUG`
  - Production: Set `LOG_LEVEL=ERROR`
- Noisy libraries (werkzeug, sqlalchemy, etc.) now default to WARNING level
- Can still override with `LOG_LEVEL=DEBUG` for full debugging

### 🎨 Frontend Updates

- **Updated Chart.js from 2.9.4 to 4.4.1**
  - Better performance
  - Modern features
  - Continued Safari compatibility
  - Security updates

### 🗂️ Database

- Removed 3 orphaned empty database files (database.db, readings.db, sensor_data.db)
- Only `monitoringhub.db` remains as the active database

### 📚 Documentation

#### Added
- `CODE_REVIEW_FIXES.md` - Detailed fix documentation
- `SECURITY.md` - Security guidelines and best practices
- `.env.template` - Environment variable template
- `setup.sh` - Automated setup script
- `CHANGELOG.md` - This file

#### Updated
- `.gitignore` - Added environment files and IDE patterns

### 🔧 Configuration Files Modified

- `backend/app.py` - Security, error handling, logging, database fixes
- `backend/models.py` - Added constants, better documentation
- `backend/usb_json_reader.py` - Fixed exception handling
- `frontend/index.html` - Updated Chart.js version
- `.gitignore` - Enhanced with security and IDE patterns

### ⚙️ Migration Guide

#### For Developers

```bash
# 1. Copy environment template
cp .env.template .env

# 2. Run automated setup
./setup.sh

# 3. Add your Gemini API key to .env
# Edit .env and set GEMINI_API_KEY=your-key

# 4. Run application
cd backend && python3 app.py
```

#### For Production

```bash
# Set environment variables (don't use .env file)
export FLASK_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export GEMINI_API_KEY="your-production-api-key"
export LOG_LEVEL="ERROR"

# Run with gunicorn
cd backend
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

### 📊 Statistics

- **Files Modified**: 5
- **Files Created**: 5
- **Lines Changed**: ~200
- **Critical Issues Fixed**: 6
- **High Priority Issues Fixed**: 5
- **Medium Priority Issues Fixed**: 2

### ⚠️ Breaking Changes

1. **Environment Variables Required**: `FLASK_SECRET_KEY` and `GEMINI_API_KEY` must now be set
2. **Logging Behavior**: Logging level now respects `LOG_LEVEL` environment variable
3. **Chart.js Update**: Frontend now uses Chart.js 4.x (should be compatible, but test thoroughly)

### 🔄 Backward Compatibility

- Existing database files remain compatible
- API endpoints unchanged
- GraphQL schema unchanged
- SSE event format unchanged

### 🧪 Testing Recommendations

Before deploying:

1. Test OCR functionality with Gemini API
2. Verify SSE connections work correctly
3. Test database operations (read/write)
4. Check Chart.js rendering in all browsers
5. Verify logging at different levels
6. Test graceful shutdown (Ctrl+C)

### 📝 Notes

- All database files in `.gitignore` should be backed up before deployment
- Review `SECURITY.md` for production deployment guidelines
- Consider implementing authentication/authorization (see recommendations)

---

## Previous Versions

No previous tracked versions. This is the first documented release after code review.

---

*Format based on [Keep a Changelog](https://keepachangelog.com/)*
