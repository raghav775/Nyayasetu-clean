import { useState, useRef } from 'react';
import {
    FileText, Wand2, RotateCcw, Download, Copy, RefreshCw, Edit3,
    Sparkles, CornerDownRight, Check, Loader2, ShieldAlert, AlertOctagon,
    Scale, BookmarkMinus, Briefcase, Users, Lock, FileSignature,
    UploadCloud, X, AlertTriangle, ListChecks, ArrowRightCircle,
    ChevronLeft, ChevronRight
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './DraftAssistant.css';

const TEMPLATE_GROUPS = [
    {
        groupTitle: 'CRIMINAL',
        templates: [
            { id: 'bail', title: 'Bail Application', icon: ShieldAlert, category: 'Petition', fields: [{ id: 'accused', label: 'Name of Accused', placeholder: 'e.g. Ramesh Kumar' }, { id: 'fir', label: 'FIR No. / Year', placeholder: 'e.g. 124/2023' }, { id: 'sections', label: 'Relevant Sections', placeholder: 'e.g. 302, 307 IPC' }, { id: 'court', label: 'Jurisdiction / Court', placeholder: 'e.g. Sessions Court, Delhi' }, { id: 'facts', label: 'Brief Defense Facts', placeholder: 'e.g. Falsely implicated...', type: 'textarea' }] },
            { id: 'anticipatory', title: 'Anticipatory Bail', icon: AlertOctagon, category: 'Petition', fields: [{ id: 'apprehended', label: 'Name of Person', placeholder: 'e.g. Suresh Singh' }, { id: 'ps', label: 'Police Station', placeholder: 'e.g. Vasant Kunj' }, { id: 'offense', label: 'Apprehended Offense', placeholder: 'e.g. 498A IPC' }, { id: 'court', label: 'Court', placeholder: 'e.g. High Court of Delhi' }, { id: 'reasons', label: 'Reasons', placeholder: 'e.g. Matrimonial dispute...', type: 'textarea' }] },
        ]
    },
    {
        groupTitle: 'CIVIL',
        templates: [
            { id: 'plaint', title: 'Civil Suit / Plaint', icon: Scale, category: 'Plaint and Written statement', fields: [{ id: 'plaintiff', label: 'Plaintiff', placeholder: 'e.g. ABC Corp.' }, { id: 'defendant', label: 'Defendant', placeholder: 'e.g. XYZ Ltd.' }, { id: 'court', label: 'Court', placeholder: 'e.g. District Court, Mumbai' }, { id: 'suitValue', label: 'Suit Value', placeholder: 'e.g. Rs. 50,00,000/-' }, { id: 'cause', label: 'Cause of Action', placeholder: 'e.g. Breach of contract...', type: 'textarea' }] },
            { id: 'injunction', title: 'Injunction Application', icon: BookmarkMinus, category: 'Civil Pleadings', fields: [{ id: 'applicant', label: 'Applicant', placeholder: 'e.g. Rahul Verma' }, { id: 'respondent', label: 'Respondent', placeholder: 'e.g. Municipal Corp.' }, { id: 'court', label: 'Court', placeholder: 'e.g. Civil Judge, Bangalore' }, { id: 'property', label: 'Subject', placeholder: 'e.g. Plot No. 42, Sector 5' }, { id: 'urgency', label: 'Grounds of Urgency', placeholder: 'e.g. Illegal demolition...', type: 'textarea' }] },
        ]
    },
    {
        groupTitle: 'CONTRACTS',
        templates: [
            { id: 'rent', title: 'Rent Agreement', icon: Briefcase, category: 'Lease Financing', fields: [{ id: 'landlord', label: 'Landlord', placeholder: 'e.g. Sunil Gupta' }, { id: 'tenant', label: 'Tenant', placeholder: 'e.g. Priya Sharma' }, { id: 'property', label: 'Property Address', placeholder: 'e.g. Flat 101, A-Wing...' }, { id: 'rent', label: 'Monthly Rent', placeholder: 'e.g. Rs. 25,000/-' }, { id: 'duration', label: 'Duration', placeholder: 'e.g. 11 Months' }] },
            { id: 'employment', title: 'Employment Contract', icon: Users, category: 'Appointment', fields: [{ id: 'company', label: 'Company', placeholder: 'e.g. TechCorp Solutions' }, { id: 'employee', label: 'Employee', placeholder: 'e.g. Anil Kumar' }, { id: 'role', label: 'Job Title', placeholder: 'e.g. Senior Engineer' }, { id: 'salary', label: 'Annual CTC', placeholder: 'e.g. Rs. 15,00,000' }, { id: 'probation', label: 'Probation Period', placeholder: 'e.g. 3 Months' }] },
            { id: 'nda', title: 'NDA', icon: Lock, category: 'Agreement', fields: [{ id: 'party1', label: 'Disclosing Party', placeholder: 'e.g. Innovator Inc.' }, { id: 'party2', label: 'Receiving Party', placeholder: 'e.g. Vendor Corp.' }, { id: 'purpose', label: 'Purpose', placeholder: 'e.g. Exploring M&A merger' }, { id: 'duration', label: 'Duration', placeholder: 'e.g. 3 Years' }] },
        ]
    },
    {
        groupTitle: 'COURT FORMS',
        templates: [
            { id: 'vakalatnama', title: 'Vakalatnama', icon: FileSignature, category: 'Vakalatnama', fields: [{ id: 'court', label: 'Court Name', placeholder: 'e.g. Supreme Court of India' }, { id: 'client', label: 'Client Name', placeholder: 'e.g. XYZ Ltd.' }, { id: 'advocate', label: 'Advocate Name', placeholder: 'e.g. Sharma Sr. Counsel' }, { id: 'caseNo', label: 'Case No.', placeholder: 'e.g. SLP (C) 1245/2026' }] },
            { id: 'affidavit', title: 'Affidavit', icon: FileText, category: 'Affidavit', fields: [{ id: 'deponent', label: 'Deponent Name', placeholder: 'e.g. Ramesh Singh' }, { id: 'age', label: 'Age / Father', placeholder: 'e.g. 45 yrs, S/o Suresh' }, { id: 'address', label: 'Address', placeholder: 'e.g. 12, Civil Lines...' }, { id: 'matter', label: 'Related Matter', placeholder: 'e.g. Support of Bail App.' }] },
        ]
    },
];

const DraftAssistant = () => {
    const { getAuthHeaders } = useAuth();
    const allTemplates = TEMPLATE_GROUPS.flatMap(g => g.templates);
    const [activeTemplateId, setActiveTemplateId] = useState('bail');
    const currentTemplate = allTemplates.find(t => t.id === activeTemplateId);

    const [formData, setFormData] = useState({});
    const [isGenerating, setIsGenerating] = useState(false);
    const [hasGenerated, setHasGenerated] = useState(false);
    const [documentContent, setDocumentContent] = useState('');
    const [sources, setSources] = useState([]);
    const [error, setError] = useState('');
    const [copied, setCopied] = useState(false);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [panelOpen, setPanelOpen] = useState(true);
    const editorRef = useRef(null);

    const switchTemplate = (id) => {
        setActiveTemplateId(id);
        setHasGenerated(false);
        setFormData({});
        setDocumentContent('');
        setSources([]);
        setError('');
    };

    const handleInputChange = (fieldId, value) => {
        setFormData(prev => ({ ...prev, [fieldId]: value }));
    };

    const buildDescription = () => {
        const parts = [`Generate a ${currentTemplate.title} with the following details:`];
        currentTemplate.fields.forEach(field => {
            if (formData[field.id]) {
                parts.push(`${field.label}: ${formData[field.id]}`);
            }
        });
        return parts.join('\n');
    };

    const triggerGeneration = async () => {
        setIsGenerating(true);
        setError('');

        try {
            const response = await fetch('/api/documents/draft', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    description: buildDescription(),
                    category: currentTemplate.category,
                    n_results: 5,
                }),
            });

            if (!response.ok) {
                let msg = 'Draft generation failed';
                try { const e = await response.json(); msg = e.detail || msg; } catch { msg = `Server error (${response.status})`; }
                throw new Error(msg);
            }

            const data = await response.json();
            setDocumentContent(data.draft);
            setSources(data.sources || []);
            setHasGenerated(true);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsGenerating(false);
        }
    };

    const handleCopy = () => {
        navigator.clipboard.writeText(documentContent);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleDownload = () => {
        const blob = new Blob([documentContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentTemplate.title.replace(/ /g, '_')}_NyayaSetu.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="workspace-layout">
            <aside className={`draft-sidebar ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
                <div className="sidebar-header-workspace">
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        {sidebarOpen && <h3>Draft Library</h3>}
                        <button
                            className="panel-toggle-btn"
                            onClick={() => setSidebarOpen(!sidebarOpen)}
                            title={sidebarOpen ? 'Collapse library' : 'Expand library'}
                        >
                            {sidebarOpen ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
                        </button>
                    </div>
                </div>
                {sidebarOpen && (
                <div className="template-list">
                    {TEMPLATE_GROUPS.map((group, gIdx) => (
                        <div key={gIdx} className="sidebar-category-group">
                            <h5 className="sidebar-category-title">{group.groupTitle}</h5>
                            {group.templates.map(t => (
                                <div
                                    key={t.id}
                                    className={`template-item ${activeTemplateId === t.id ? 'active' : ''}`}
                                    onClick={() => switchTemplate(t.id)}
                                >
                                    <t.icon size={18} className="template-icon" />
                                    <div><h4>{t.title}</h4></div>
                                </div>
                            ))}
                        </div>
                    ))}
                </div>
                )}
            </aside>

            <main className="editor-area">
                {!hasGenerated && !isGenerating && (
                    <div className="form-draft-container animate-fade-in">
                        <div className="standard-form-wrapper">
                            <div className="draft-form-header">
                                <h2>Draft: {currentTemplate.title}</h2>
                                <p>Fill in the details below. NyayaSetu AI will generate a complete legal document using 1,841 real Indian legal templates.</p>
                            </div>
                            <div className="draft-form-body">
                                {error && (
                                    <div style={{ padding: '0.75rem', background: '#fee2e2', borderRadius: '6px', color: '#991b1b', marginBottom: '1rem', fontSize: '0.9rem' }}>
                                        {error}
                                    </div>
                                )}
                                <div className="form-grid-premium">
                                    {currentTemplate.fields.map(field => (
                                        <div key={field.id} className={`form-group-premium ${field.type === 'textarea' ? 'full-width' : ''}`}>
                                            <label>{field.label}</label>
                                            {field.type === 'textarea' ? (
                                                <textarea
                                                    rows="3"
                                                    placeholder={field.placeholder}
                                                    value={formData[field.id] || ''}
                                                    onChange={(e) => handleInputChange(field.id, e.target.value)}
                                                />
                                            ) : (
                                                <input
                                                    type="text"
                                                    placeholder={field.placeholder}
                                                    value={formData[field.id] || ''}
                                                    onChange={(e) => handleInputChange(field.id, e.target.value)}
                                                />
                                            )}
                                        </div>
                                    ))}
                                </div>
                                <button className="smart-generate-btn" onClick={triggerGeneration}>
                                    <Sparkles size={20} /> Generate Draft with AI
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {isGenerating && (
                    <div className="generation-loading-state animate-fade-in">
                        <div className="spinner-ring">
                            <Loader2 size={48} className="spin text-primary" />
                        </div>
                        <h3>Generating Your Document...</h3>
                        <p className="loading-stage-text">AI is analyzing 1,841 legal templates and crafting your draft...</p>
                    </div>
                )}

                {hasGenerated && (
                    <div className="canvas-wrapper">
                        <div className="editor-controls animate-fade-in">
                            <div className="editor-actions ml-auto">
                                <button className="editor-action-btn secondary" onClick={() => setHasGenerated(false)}>
                                    <Edit3 size={15} /> Edit Details
                                </button>
                                <button className="editor-action-btn secondary" onClick={triggerGeneration}>
                                    <RefreshCw size={15} /> Regenerate
                                </button>
                                <button className="editor-action-btn secondary" onClick={handleCopy}>
                                    {copied ? <><Check size={15} /> Copied!</> : <><Copy size={15} /> Copy</>}
                                </button>
                                <button className="editor-action-btn primary" onClick={handleDownload}>
                                    <Download size={15} /> Download
                                </button>
                            </div>
                        </div>
                        <div className="a4-canvas animate-fade-in">
                            <div
                                className="a4-page"
                                ref={editorRef}
                                contentEditable
                                suppressContentEditableWarning
                                onInput={(e) => setDocumentContent(e.currentTarget.innerText)}
                                style={{ whiteSpace: 'pre-wrap' }}
                            >
                                {documentContent}
                            </div>
                        </div>
                    </div>
                )}
            </main>

            <aside className={`ai-insight-panel ${panelOpen ? '' : 'panel-collapsed'}`}>
                <div className="ai-panel-header">
                    <button
                        className="panel-toggle-btn panel-toggle-btn-right"
                        onClick={() => setPanelOpen(!panelOpen)}
                        title={panelOpen ? 'Collapse sources' : 'Expand sources'}
                    >
                        {panelOpen ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
                    </button>
                    {panelOpen && (
                        <>
                            <Sparkles size={18} className="text-primary" />
                            <h3>Reference Sources</h3>
                        </>
                    )}
                </div>
                {panelOpen && (
                <div className="ai-suggestions-feed">
                    {!hasGenerated && (
                        <div className="empty-suggestions">
                            <Wand2 size={32} className="text-secondary mx-auto mb-4 opacity-50" />
                            <p>Generate a draft to see which real legal templates were used as reference.</p>
                        </div>
                    )}
                    {hasGenerated && sources.length > 0 && (
                        <div className="animate-fade-in">
                            <p style={{ fontSize: '0.8rem', color: '#6b7280', marginBottom: '0.75rem' }}>
                                AI referenced these real documents from your legal database:
                            </p>
                            {sources.map((s, i) => (
                                <div key={i} className="suggestion-card">
                                    <h5><CornerDownRight size={14} className="text-secondary" /> {s.filename}</h5>
                                    <p>Category: {s.category} | Match: {(s.score * 100).toFixed(0)}%</p>
                                </div>
                            ))}
                        </div>
                    )}
                    {hasGenerated && sources.length === 0 && (
                        <p style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                            Run ingest.py to load legal templates for reference-based generation.
                        </p>
                    )}
                </div>
                )}
            </aside>
        </div>
    );
};

export default DraftAssistant;
