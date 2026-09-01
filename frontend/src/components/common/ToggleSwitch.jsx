import React from 'react';

export default function ToggleSwitch({ checked, onChange, id, label, ariaLabel }) {
  return (
    <label htmlFor={id} className="relative inline-flex items-center cursor-pointer select-none">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="sr-only peer"
        aria-label={ariaLabel || label}
      />
      <div
        className="w-11 h-6 bg-surface-variant rounded-full peer 
                   peer-focus:ring-2 peer-focus:ring-coral-accent/50 
                   peer-checked:bg-coral-accent
                   after:content-[''] after:absolute after:top-0.5 after:left-[2px] 
                   after:bg-white after:border-outline-variant after:border 
                   after:rounded-full after:h-5 after:w-5 after:transition-all 
                   peer-checked:after:translate-x-full peer-checked:after:border-white"
      />
    </label>
  );
}
#documind
              
