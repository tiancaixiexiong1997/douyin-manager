import { useEffect, useMemo, useRef, useState } from 'react';

import { ChevronDown } from './Icons';
import './CustomSelect.css';

export type CustomSelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

type CustomSelectProps = {
  value: string;
  options: CustomSelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  triggerClassName?: string;
  dropdownClassName?: string;
  optionClassName?: string;
  disabled?: boolean;
};

function joinClasses(...classes: Array<string | undefined | false>) {
  return classes.filter(Boolean).join(' ');
}

export function CustomSelect({
  value,
  options,
  onChange,
  placeholder,
  className,
  triggerClassName,
  dropdownClassName,
  optionClassName,
  disabled = false,
}: CustomSelectProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const selectedOption = useMemo(
    () => options.find((option) => option.value === value),
    [options, value]
  );

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={joinClasses('ui-select', open && 'is-open', className)}>
      <button
        type="button"
        className={joinClasses('ui-select-trigger', triggerClassName)}
        onClick={() => !disabled && setOpen((current) => !current)}
        aria-expanded={open}
        aria-haspopup="listbox"
        disabled={disabled}
      >
        <span className={joinClasses('ui-select-value', !selectedOption && 'is-placeholder')}>
          {selectedOption?.label || placeholder || '请选择'}
        </span>
        <ChevronDown className="ui-select-icon" size={16} />
      </button>

      {open && (
        <div className={joinClasses('ui-select-dropdown', dropdownClassName)} role="listbox">
          {options.map((option) => {
            const selected = option.value === value;
            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={selected}
                disabled={option.disabled}
                className={joinClasses(
                  'ui-select-option',
                  selected && 'is-selected',
                  optionClassName
                )}
                onClick={() => {
                  if (option.disabled) return;
                  onChange(option.value);
                  setOpen(false);
                }}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
