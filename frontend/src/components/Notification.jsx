import React from 'react';
import { CheckCircle, X, Sparkles } from 'lucide-react';

export default function Notification({ message, type, visible, onClose }) {
  if (!visible && !message) return null;

  const icons = {
    success: <CheckCircle className="toast-icon success" />,
    error: <X className="toast-icon error" />,
    info: <Sparkles className="toast-icon info" />
  };

  return (
    <div className={`toast-notification glass ${type} ${visible ? 'visible' : 'hidden'}`}>
      <div className="toast-content">
        {icons[type] || icons.info}
        <span className="toast-message">{message}</span>
      </div>
      <button className="toast-close" onClick={onClose}>
        <X size={14} />
      </button>
    </div>
  );
}
