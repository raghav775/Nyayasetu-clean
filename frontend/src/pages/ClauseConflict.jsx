import { useState, useRef } from 'react';
import {
    UploadCloud, X, Plus, FileText, AlertTriangle,
    ShieldAlert, Loader2, Sparkles, AlertCircle, FileSearch, ArrowRight
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './ClauseConflict.css';

const ClauseConflict = () => {
    const { getAuthHeaders } = useAuth();
    const [parties, setParties] = useState([
        { id: 'party-1', name: 'Party 1', files: [], content: '' },
        { id: 'party-2', name: 'Party 2', files: [], content: '' },
    ]);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [analysisResults, setAnalysisResults] = useState(null);
    const [error, setError] = useState('');
    const fileInputRefs = useRef({});

    const handleAddParty = () => {
        const newId = `party-${Date.now()}`;
        setParties([...parties, { id: newId, name: `Party ${parties.length + 1}`, files: [], content: '' }]);
    };

    const handleRemoveParty = (idToRemove) => {
        if (parties.length <= 2) return;
        setParties(parties.filter(p => p.id !== idToRemove).map((p, idx) => ({ ...p, name: `Party ${idx + 1}` })));
    };

    const updatePartyName = (id, newName) => {
        setParties(parties.map(p => p.id === id ? { ...p, name: newName } : p));
    };

    const readFileAsText = async (file) => {
        const ext = file.name.split('.').pop().toLowerCase();
        
        if (ext === 'txt') {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve(e.target.result);
                reader.onerror = reject;
                reader.readAsText(file, 'utf-8');
            });
        }
    
        if (ext === 'pdf') {
            const pdfjsLib = await import('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.2.67/pdf.min.mjs');
            pdfjsLib.GlobalWorkerOptions.workerSrc =
                'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.2.67/pdf.worker.min.mjs';
            const arrayBuffer = await file.arrayBuffer();
            const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
            let fullText = '';
            for (let i = 1; i <= pdf.numPages; i++) {
                const page = await pdf.getPage(i);
                const content = await page.getTextContent();
                fullText += content.items.map(item => item.str).join(' ') + '\n';
            }
            return fullText;
        }
    
        if (ext === 'doc' || ext === 'docx') {
            // Load mammoth as a script tag so it attaches to window.mammoth globally
            await new Promise((resolve, reject) => {
                if (window.mammoth) return resolve();  // already loaded
                const script = document.createElement('script');
                script.src = 'https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.8.0/mammoth.browser.min.js';
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });
            const arrayBuffer = await file.arrayBuffer();
            const result = await window.mammoth.extractRawText({ arrayBuffer });
            return result.value;
        }
    
        throw new Error(`Unsupported file type: .${ext}`);
};  

    const handleFileUpload = async (e, partyId) => {
        const uploadedFiles = Array.from(e.target.files);
        if (!uploadedFiles.length) return;

        let combinedContent = '';
        const mappedFiles = [];

        for (const file of uploadedFiles) {
            try {
                const text = await readFileAsText(file);
                combinedContent += `\n\n=== ${file.name} ===\n${text}`;
                mappedFiles.push({
                    id: `file-${Date.now()}-${Math.random()}`,
                    name: file.name,
                    size: (file.size / 1024).toFixed(1) + ' KB',
                });
            } catch {
                mappedFiles.push({
                    id: `file-${Date.now()}-${Math.random()}`,
                    name: file.name,
                    size: (file.size / 1024).toFixed(1) + ' KB',
                });
            }
        }

        setParties(parties.map(p => {
            if (p.id === partyId) {
                return { ...p, files: [...p.files, ...mappedFiles], content: p.content + combinedContent };
            }
            return p;
        }));

        if (fileInputRefs.current[partyId]) fileInputRefs.current[partyId].value = null;
    };

    const handleRemoveFile = (partyId, fileId) => {
        setParties(parties.map(p => {
            if (p.id === partyId) return { ...p, files: p.files.filter(f => f.id !== fileId) };
            return p;
        }));
    };

    const updatePartyContent = (partyId, text) => {
        setParties(parties.map(p =>
            p.id === partyId ? { ...p, content: text } : p
        ));
    };

    const validParties = parties.filter(p => p.content && p.content.trim().length > 20);
    const canAnalyze = validParties.length >= 2;

    const triggerConflictAnalysis = async () => {
        if (!canAnalyze) return;
        setIsAnalyzing(true);
        setAnalysisResults(null);
        setError('');

        try {
            const response = await fetch('/api/documents/scan-contradictions', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    document_a: `${validParties[0].name}:\n${validParties[0].content}`,
                    document_b: `${validParties[1].name}:\n${validParties[1].content}`,
                }),
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Analysis failed');
            }

            const data = await response.json();
            setAnalysisResults(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsAnalyzing(false);
        }
    };

    return (
        <div className="conflict-workspace-layout">
            <header className="conflict-header-premium">
                <div className="header-icon-wrapper"><ShieldAlert size={28} className="text-primary" /></div>
                <div className="header-text-block">
                    <h2>Multi-Party Contract Analyzer</h2>
                    <p>Upload a TXT file or paste contract text directly. AI will detect contradictions, liability conflicts, and jurisdictional disputes instantly.</p>
                </div>
            </header>

            <main className="conflict-main-content">
                {!isAnalyzing && !analysisResults && (
                    <div className="upload-matrix-stage animate-fade-in">
                        {error && (
                            <div className="error-banner">
                                {error}
                            </div>
                        )}
                        <div className="party-cards-grid">
                            {parties.map((party) => (
                                <div key={party.id} className="party-card-premium">
                                    <div className="party-card-header">
                                        <input
                                            type="text"
                                            value={party.name}
                                            onChange={(e) => updatePartyName(party.id, e.target.value)}
                                            className="party-name-input"
                                            placeholder="Enter Party Name..."
                                        />
                                        {parties.length > 2 && (
                                            <button className="remove-party-btn" onClick={() => handleRemoveParty(party.id)}>
                                                <X size={18} />
                                            </button>
                                        )}
                                    </div>

                                    <div className="party-upload-zone" onClick={() => fileInputRefs.current[party.id]?.click()}>
                                        <input
                                            type="file"
                                            multiple
                                            accept=".txt,.pdf,.doc,.docx"
                                            className="hidden-file-input"
                                            ref={(el) => fileInputRefs.current[party.id] = el}
                                            onChange={(e) => handleFileUpload(e, party.id)}
                                        />
                                        <UploadCloud size={32} className="upload-icon-faded" />
                                        <p>Click to upload a contract file</p>
                                        <span className="upload-subtext">Supported: TXT, PDF, DOC, DOCX</span>
                                    </div>

                                    <div className="paste-divider">
                                        <span>or paste text directly</span>
                                    </div>

                                    <textarea
                                        className="party-text-input"
                                        placeholder="Paste contract text here..."
                                        value={party.content}
                                        onChange={(e) => updatePartyContent(party.id, e.target.value)}
                                        rows={6}
                                    />

                                    {party.files.length > 0 && (
                                        <div className="party-files-list">
                                            {party.files.map(file => (
                                                <div key={file.id} className="uploaded-file-row">
                                                    <FileText size={16} className="text-primary" />
                                                    <span className="file-name-truncate">{file.name}</span>
                                                    <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>{file.size}</span>
                                                    <button
                                                        className="remove-file-btn"
                                                        onClick={(e) => { e.stopPropagation(); handleRemoveFile(party.id, file.id); }}
                                                    >
                                                        <X size={14} />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>

                        <div className="matrix-controls-strip">
                            <button className="add-party-ghost-btn" onClick={handleAddParty}>
                                <Plus size={18} /> Add Another Party
                            </button>
                            <button
                                className={`analyze-matrix-btn ${canAnalyze ? 'active' : 'disabled'}`}
                                onClick={triggerConflictAnalysis}
                                disabled={!canAnalyze}
                            >
                                <Sparkles size={20} />
                                {canAnalyze
                                    ? `Analyze ${validParties.length} Parties`
                                    : 'Add text to at least 2 parties'}
                            </button>
                        </div>
                    </div>
                )}

                {isAnalyzing && (
                    <div className="matrix-loading-state animate-fade-in">
                        <div className="spinner-ring">
                            <Loader2 size={56} className="spin text-primary" />
                        </div>
                        <h3>AI Contradiction Analysis Running</h3>
                        <p className="loading-stage-text">
                            Cross-referencing {validParties.map(p => p.name).join(' vs ')} for legal contradictions...
                        </p>
                    </div>
                )}

                {!isAnalyzing && analysisResults && (
                    <div className="matrix-results-stage animate-fade-in">
                        <div className="results-header-actions">
                            <h3>
                                <FileSearch size={22} className="text-primary inline mr-2" />
                                Analysis Complete — {analysisResults.overall_compatibility}
                            </h3>
                            <button className="reset-matrix-btn" onClick={() => { setAnalysisResults(null); setError(''); }}>
                                Analyze Again
                            </button>
                        </div>

                        <div className="results-metrics-strip">
                            <div className="metric-box">
                                <span className="metric-value">{analysisResults.total_contradictions}</span>
                                <span className="metric-label">Contradictions Found</span>
                            </div>
                            <div className="metric-box">
                                <span className="metric-value text-red-600">
                                    {analysisResults.contradictions.filter(c =>
                                        c.suggested_resolution?.length > 100
                                    ).length}
                                </span>
                                <span className="metric-label">Need Attention</span>
                            </div>
                            <div className="metric-box">
                                <span className="metric-value">{validParties.length}</span>
                                <span className="metric-label">Parties Analyzed</span>
                            </div>
                        </div>

                        <div className="conflicts-feed">
                            {analysisResults.contradictions.length === 0 && (
                                <div style={{ textAlign: 'center', padding: '2rem', color: '#6b7280' }}>
                                    <AlertCircle size={32} style={{ margin: '0 auto 0.5rem' }} />
                                    <p>No contradictions detected between the documents.</p>
                                </div>
                            )}
                            {analysisResults.contradictions.map((conflict, i) => (
                                <div key={i} className="conflict-result-card">
                                    <div className="conflict-result-header">
                                        <div className="conflict-party-badge">{conflict.clause}</div>
                                        <div className="severity-badge badge-high">
                                            <ShieldAlert size={14} /> Contradiction
                                        </div>
                                    </div>
                                    <div className="conflict-clauses-split">
                                        <div className="clause-box">
                                            <span className="clause-source-label">Party A Position</span>
                                            <p className="clause-text">"{conflict.party_a_position}"</p>
                                        </div>
                                        <div className="clause-divider-icon">
                                            <ArrowRight size={24} className="text-red-500 mx-2" />
                                        </div>
                                        <div className="clause-box red-tint">
                                            <span className="clause-source-label">Party B Position</span>
                                            <p className="clause-text">"{conflict.party_b_position}"</p>
                                        </div>
                                    </div>
                                    <div className="conflict-implication-box">
                                        <h4>Suggested Resolution:</h4>
                                        <p>{conflict.suggested_resolution}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
};

export default ClauseConflict;