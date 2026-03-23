import React from 'react';
import { FACTORS } from '../constants';

export default function FactorPills({ value, onChange }) {
  return (
    <div className="factor-pills">
      {FACTORS.map(f => (
        <button
          key={f.id}
          className={`factor-pill${value === f.id ? ' active' : ''}`}
          onClick={() => onChange(f.id)}
        >
          {f.label}
        </button>
      ))}
    </div>
  );
}
