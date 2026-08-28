import { QUERY_CATEGORIES } from "../data/queryCategories";

export default function QueryCategories({ onTry }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
        Sample Questions by Category
      </h3>
      <div className="grid gap-4 md:grid-cols-2">
        {QUERY_CATEGORIES.map((cat) => (
          <div key={cat.id} className="rounded-md border border-slate-100 bg-slate-50 p-3">
            <p className="text-sm font-medium text-slate-800">{cat.title}</p>
            <p className="mt-1 text-xs text-slate-500">{cat.blurb}</p>
            <ul className="mt-2 space-y-1.5">
              {cat.examples.map((q) => (
                <li key={q}>
                  <button
                    onClick={() => onTry(q)}
                    className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-left text-xs text-slate-600 hover:border-brand-400 hover:text-brand-700"
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
