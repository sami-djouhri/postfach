import { useState } from 'react';

interface Props {
  onSearch: (query: string) => void;
  placeholder?: string;
}

export default function SearchBar({ onSearch, placeholder = 'Suchen...' }: Props) {
  const [value, setValue] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim()) {
      onSearch(value.trim());
    }
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          if (!e.target.value.trim()) onSearch('');
        }}
        placeholder={placeholder}
        className="search-input"
      />
      {value && (
        <button
          type="button"
          className="search-clear"
          onClick={() => { setValue(''); onSearch(''); }}
        >
          &times;
        </button>
      )}
    </form>
  );
}
