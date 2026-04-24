import React, { useState, useEffect, useCallback, useRef } from 'react';
import './index.css';

interface Book {
  isbn: string;
  score: number;
  title: string;
  author: string;
  publisher: string;
  year: string;
  image_url: string;
  rating: string;
}

const API_BASE = 'http://localhost:8000';

// Custom SVG Icons (No Emojis)
const IconSearch = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
  </svg>
);

const IconPlus = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line>
  </svg>
);

const IconLibrary = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
  </svg>
);

const App: React.FC = () => {
  const [view, setView] = useState<'discover' | 'add'>('discover');
  const [hasSearched, setHasSearched] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Book[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [latency, setLatency] = useState(0);

  const [failedImages, setFailedImages] = useState<Set<string>>(new Set());
  const [ratingInputs, setRatingInputs] = useState<Record<string, number>>({});
  const [apiKey, setApiKey] = useState('');
  
  const [authModal, setAuthModal] = useState<{isOpen: boolean, action: 'add' | 'rate', isbn?: string, pendingRating?: number}>({isOpen: false, action: 'add'});
  const [tempKey, setTempKey] = useState('');

  const [formData, setFormData] = useState({
    title: '', author: '', publisher: '', year: '2026', rating: '8.5', image_url: ''
  });

  const appRef = useRef<HTMLDivElement>(null);

  // 1. Cursor Tracking Logic
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (appRef.current) {
        appRef.current.style.setProperty('--mouse-x', `${e.clientX}px`);
        appRef.current.style.setProperty('--mouse-y', `${e.clientY}px`);
      }
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  // 2. Autocomplete Logic
  useEffect(() => {
    if (query.length < 2) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/suggest?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        setSuggestions(data.suggestions || []);
      } catch (err) { console.error(err); }
    }, 150);
    return () => clearTimeout(timer);
  }, [query]);

  const handleSearch = useCallback(async (q: string) => {
    const term = q || query;
    if (!term.trim()) return;
    
    setLoading(true);
    setHasSearched(true);
    setShowSuggestions(false);
    setFailedImages(new Set()); // Reset failed images on fresh search
    
    try {
      const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(term)}`);
      const data = await res.json();
      
      // Feature: Clear results if none found
      if (!data.results || data.results.length === 0) {
        setResults([]);
      } else {
        setResults(data.results);
      }
      setLatency(data.latency_ms);
    } catch (err) { 
      console.error(err);
      setResults([]); 
    } finally { 
      setLoading(false); 
    }
  }, [query]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      setActiveSuggestion(prev => Math.min(prev + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      setActiveSuggestion(prev => Math.max(prev - 1, -1));
    } else if (e.key === 'Enter') {
      if (activeSuggestion >= 0) {
        const selected = suggestions[activeSuggestion];
        setQuery(selected);
        handleSearch(selected);
      } else {
        handleSearch(query);
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const handleCommit = async () => {
    try {
      const res = await fetch(`${API_BASE}/books`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-api-key': apiKey },
        body: JSON.stringify({ ...formData, rating: parseFloat(formData.rating) })
      });
      if (res.status === 401) {
        alert("Unauthorized! Invalid API Key.");
        setApiKey('');
        return;
      }
      const data = await res.json();
      if (data.status === 'success') {
        setFormData({ title: '', author: '', publisher: '', year: '2026', rating: '8.5', image_url: '' });
        setView('discover');
      }
    } catch (err) { console.error(err); }
  };

  const handleRateBook = async (isbn: string, newRating: number) => {
    if (!apiKey) {
      setAuthModal({isOpen: true, action: 'rate', isbn, pendingRating: newRating});
      return;
    }
    await executeRate(isbn, newRating, apiKey);
  };

  const executeRate = async (isbn: string, newRating: number, keyToUse: string) => {
    try {
      const res = await fetch(`${API_BASE}/books/${isbn}/rate?rating=${newRating}`, { 
          method: 'POST',
          headers: { 'x-api-key': keyToUse }
      });
      if (res.status === 401) {
          alert("Unauthorized! Invalid API Key.");
          setApiKey('');
          return;
      }
      if (res.ok) {
        setApiKey(keyToUse);
        const data = await res.json();
        const updatedRating = data.new_rating || newRating;
        setResults(prev => prev.map(b => b.isbn === isbn ? { ...b, rating: String(updatedRating) } : b));
        setAuthModal({isOpen: false, action: 'add'});
        setTempKey('');
      }
    } catch (err) { console.error(err); }
  };

  const handleAuthAndAdd = () => {
    if (apiKey) {
        setView('add');
    } else {
        setAuthModal({isOpen: true, action: 'add'});
    }
  };

  const onModalSubmit = () => {
    if (!tempKey.trim()) return;
    if (authModal.action === 'add') {
        setApiKey(tempKey);
        setView('add');
        setAuthModal({isOpen: false, action: 'add'});
        setTempKey('');
    } else if (authModal.action === 'rate' && authModal.isbn && authModal.pendingRating) {
        executeRate(authModal.isbn, authModal.pendingRating, tempKey);
    }
  };

  const activeResults = [...results].sort((a, b) => {
    const aFailed = failedImages.has(a.isbn);
    const bFailed = failedImages.has(b.isbn);
    if (aFailed && !bFailed) return 1;
    if (!aFailed && bFailed) return -1;
    return 0;
  });

  return (
    <div className="app-wrapper" ref={appRef}>
      <div className="spotlight-bg" />
      
      <div className="sketch-container">
        {[...Array(8)].map((_, i) => (
          <div 
            key={i} className="sketch-book" 
            style={{ 
              left: `${Math.random() * 80 + 10}%`, 
              animationDelay: `${Math.random() * 20}s`,
              fontSize: `${Math.random() * 2 + 1}rem`
            }}
          >
            <IconLibrary />
          </div>
        ))}
      </div>

      {view === 'add' ? (
        <div className="form-v2">
          <h1 className="form-title">Register New Folio</h1>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '3rem' }}>
            <div>
                <div className="field-v2">
                <label className="label-v2">Title</label>
                <input type="text" className="input-v2-form" value={formData.title} onChange={e => setFormData({...formData, title: e.target.value})} />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                <div className="field-v2"><label className="label-v2">Author</label>
                    <input type="text" className="input-v2-form" value={formData.author} onChange={e => setFormData({...formData, author: e.target.value})} />
                </div>
                <div className="field-v2"><label className="label-v2">Publisher</label>
                    <input type="text" className="input-v2-form" value={formData.publisher} onChange={e => setFormData({...formData, publisher: e.target.value})} />
                </div>
                </div>
                <div className="field-v2">
                <label className="label-v2">Cover Image URL</label>
                <input type="text" className="input-v2-form" value={formData.image_url} onChange={e => setFormData({...formData, image_url: e.target.value})} />
                </div>
                <div className="field-v2">
                <label className="label-v2">Year of Publication</label>
                <input type="text" className="input-v2-form" value={formData.year} onChange={e => setFormData({...formData, year: e.target.value})} />
                </div>
                <div className="field-v2">
                  <label className="label-v2">Rating</label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                    <input 
                      type="range" className="slider-v2" min="1" max="10" step="0.5"
                      value={formData.rating} 
                      onChange={e => setFormData({...formData, rating: e.target.value})} 
                      style={{ flexGrow: 1 }}
                    />
                    <span style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--color-accent)' }}>{formData.rating}</span>
                  </div>
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <label className="label-v2">Folio Preview</label>
                <div style={{ 
                    width: '200px', height: '300px', 
                    background: 'var(--color-base)', 
                    border: '1px solid var(--glass-border)',
                    borderRadius: '12px',
                    overflow: 'hidden',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                    {formData.image_url ? (
                        <img 
                            src={formData.image_url} 
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                            onError={(e) => (e.currentTarget.src = 'https://via.placeholder.com/200x300?text=Invalid+Link')}
                            alt="Preview" 
                        />
                    ) : (
                        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>No URL Provided</span>
                    )}
                </div>
            </div>
          </div>
          
          <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
            <button className="btn-v2" onClick={handleCommit}>Archive Folio</button>
            <button className="btn-v2 btn-v2-ghost" onClick={() => setView('discover')}>Discard</button>
          </div>
        </div>
      ) : (
        <>
          {/* Transitioning Search Section */}
          {!hasSearched ? (
            <section className="hero-v2">
              <div className="hero-badge">Discover Archival Literature</div>
              <div className="brand-v2">READ <span>DIRECT</span></div>
              <p className="hero-subtitle">Instantly search millions of folios, manuscripts, and out-of-print books.</p>
              
              <div className="search-container-v2">
                <div className="search-icon-v2"><IconSearch /></div>
                <input 
                  type="text" className="input-v2" placeholder="Scan records..." 
                  value={query} onChange={e => { setQuery(e.target.value); setShowSuggestions(true); setActiveSuggestion(-1); }}
                  onKeyDown={onKeyDown} autoFocus
                />
                {showSuggestions && suggestions.length > 0 && (
                  <div className="dropdown-v2">
                    {suggestions.map((s, i) => (
                      <div 
                        key={i} className={`suggestion-v2 ${i === activeSuggestion ? 'active' : ''}`}
                        onClick={() => { setQuery(s); handleSearch(s); }}
                      >{s}</div>
                    ))}
                  </div>
                )}
              </div>
              
              <div className="hero-chips">
                <span onClick={() => {setQuery('History'); handleSearch('History');}}>History</span>
                <span onClick={() => {setQuery('Science Fiction'); handleSearch('Science Fiction');}}>Science Fiction</span>
                <span onClick={() => {setQuery('Philosophy'); handleSearch('Philosophy');}}>Philosophy</span>
                <span onClick={() => {setQuery('Classic Art'); handleSearch('Classic Art');}}>Classic Art</span>
              </div>
            </section>
          ) : (
            <>
              <header className="header-v2">
                <div className="brand-v2" onClick={() => {setHasSearched(false); setResults([]); setQuery('');}}>READ<span>DIRECT</span></div>
                <div className="search-container-v2" style={{ maxWidth: '500px' }}>
                  <div className="search-icon-v2"><IconSearch /></div>
                  <input 
                    type="text" className="input-v2" value={query} 
                    onChange={e => { setQuery(e.target.value); setShowSuggestions(true); setActiveSuggestion(-1); }}
                    onKeyDown={onKeyDown}
                  />
                  {showSuggestions && suggestions.length > 0 && (
                    <div className="dropdown-v2">
                      {suggestions.map((s, i) => (
                        <div 
                          key={i} className={`suggestion-v2 ${i === activeSuggestion ? 'active' : ''}`}
                          onClick={() => { setQuery(s); handleSearch(s); }}
                        >{s}</div>
                      ))}
                    </div>
                  )}
                </div>
                <div style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>{latency}ms</div>
              </header>

              <main className="bento-grid">
                {loading && <div style={{gridColumn: '1/-1', textAlign: 'center', padding: '5rem', color: 'var(--color-accent)'}}>Indexing results...</div>}
                {!loading && activeResults.map((book) => (
                  <article key={book.isbn} className="bento-card">
                    <div className="bento-img-wrapper">
                      {failedImages.has(book.isbn) ? (
                        <div className="bento-img-fallback">
                          <IconLibrary />
                          <span>Image not available</span>
                        </div>
                      ) : (
                        <img 
                          className="bento-img"
                          loading="lazy"
                          decoding="async"
                          src={`${API_BASE}/proxy-image?url=${encodeURIComponent(book.image_url)}`} 
                          onError={() => setFailedImages(prev => new Set(prev).add(book.isbn))}
                          alt={book.title}
                        />
                      )}
                    </div>
                    <div className="bento-info">
                      <h2>{book.title}</h2>
                      <div className="bento-author">by {book.author}</div>
                      <div className="bento-meta">
                        {book.publisher} • {book.year}<br/>
                        ISBN: {book.isbn}
                      </div>
                      <div className="rating-section" style={{ marginTop: 'auto' }}>
                        <div style={{ fontWeight: '700', color: 'white', marginBottom: '0.5rem' }}>
                            {Number(book.rating) === 0 ? <span style={{color: 'var(--color-text-muted)', fontWeight: '400'}}>Not Rated</span> : `${book.rating}/10`}
                        </div>
                        <div className="rate-action" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                            <input 
                                type="range" className="slider-v2 slider-small" min="1" max="10" step="0.5"
                                value={ratingInputs[book.isbn] || Number(book.rating) || 5}
                                onChange={e => setRatingInputs({...ratingInputs, [book.isbn]: parseFloat(e.target.value)})}
                                style={{ width: '80px' }}
                            />
                            <span style={{ fontSize: '0.85rem' }}>{ratingInputs[book.isbn] || Number(book.rating) || 5}</span>
                            <button className="btn-rate" onClick={() => handleRateBook(book.isbn, ratingInputs[book.isbn] || Number(book.rating) || 5)}>Rate</button>
                        </div>
                      </div>
                    </div>
                  </article>
                ))}
                {!loading && hasSearched && results.length === 0 && (
                  <div style={{gridColumn: '1/-1', textAlign: 'center', padding: '10rem'}}>
                    <div style={{fontSize: '4rem', opacity: 0.1, marginBottom: '2rem'}}><IconLibrary/></div>
                    <div style={{color: 'var(--color-text-muted)'}}>No archival matches found for "{query}"</div>
                  </div>
                )}
              </main>
            </>
          )}

          <div className="action-btn-main" title="Contribute New Folio" onClick={handleAuthAndAdd}>
            <span>Contribute Folio</span>
          </div>
        </>
      )}

      {authModal.isOpen && (
        <div className="modal-overlay">
            <div className="modal-content">
                <h2 style={{fontFamily: 'var(--font-serif)', marginBottom: '0.5rem', fontSize: '2rem'}}>Authorization Required</h2>
                <p style={{color: 'var(--color-text-secondary)', marginBottom: '1.5rem', fontSize: '0.9rem'}}>Please enter the administrator key to grant database write access.</p>
                <input 
                  type="password" value={tempKey} onChange={e => setTempKey(e.target.value)} 
                  className="input-v2" autoFocus placeholder="Enter code..."
                  onKeyDown={e => e.key === 'Enter' && onModalSubmit()}
                />
                <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
                    <button className="btn-v2" onClick={onModalSubmit}>Authenticate</button>
                    <button className="btn-v2 btn-v2-ghost" onClick={() => {setAuthModal({isOpen: false, action: 'add'}); setTempKey('');}}>Cancel</button>
                </div>
            </div>
        </div>
      )}
    </div>
  );
};

export default App;
