import * as React from 'react'
import {ClientOnly} from './clientonly'

type Kind = "object" | "html" | "image" | "plotly" | "blob" | "opaque"

interface Html {
    __kind__: 'html';
    tag: string;
    attrs: { [k: string]: any };
    children: VisualObject[];
}

interface Opaque {
    __kind__: 'opaque';
    __class__: string;
    repr?: string;
}

interface Basic {
    __kind__?: 'object';
    __class__?: string;
    // other things go here.
}


interface Blob {
    __kind__: 'blob'
    // [todo]
}

interface Plotly {
    __kind__: 'plotly';
    /** Plotly JSON encoding. */
    value: string;
}


export type VisualObject = Html | Opaque | Basic | Plotly | Blob | number | string | boolean | null | VisualObject[] | { [k: string]: VisualObject }

function isList(v: VisualObject): v is VisualObject[] {
    return v instanceof Array
}

function isDict(v: VisualObject): v is { [k: string]: VisualObject } {
    if (typeof v !== 'object') {
        return false
    }
    if (!v) {
        return false
    }
    if (Object.hasOwnProperty.call(v, '__kind__')) {
        return false
    }
    return true
}

/* The Show function renders these visual objects.

The tricky bit is figuring out how much information to show to the user.

- [ ] There should be a 'fully expanded' modal that lets you see the whole unabridged object.
- [ ] something like responsive design should be used, where each object has various representations depending on the size available.
- [ ] should be a mode : 'inline' | 'block' dictating whether there are multiple lines.

https://github.com/remix-run/remix/discussions/2936

*/

// @ts-ignore
const Plot = React.lazy(() => import('./react-plotly'))

export function Show(props: { o: VisualObject, depth?: number }) {
    const depth = props.depth ?? 0
    const o = props.o
    if (o === null) {
        return <span>None</span>
    } else if (typeof o === 'boolean') {
        if (o) {
            return <span>True</span>
        } else {
            return <span>False</span>
        }
    } else if (typeof o === 'number') {
        return <span>{o}</span>
    } else if (typeof o === 'string') {
        // [todo] if too long?
        return <span>{o}</span>
    } else if (isList(o)) {
        // [todo] too long? collapsible?
        const S = 10
        const items = o.slice(0, 10).map((x, i) => <Show key={i} o={x} depth={depth + 1} />)

        if (o.length > S) {
            items.push(<span>...</span>)
        }
        return <span>[{interlace(items, <>, </>)}]</span>
    } else if (isDict(o) || o.__kind__ === 'object') {
        // [todo] should pretty print on multiple lines if there is space.
        const keys = Object.getOwnPropertyNames(o).filter(k => k.startsWith('__'))
        return <span>{"{"}{keys.map(k => <span key={k}>{k} : <Show o={(o as any)[k]} depth={depth + 1} /></span>)}{"}"}</span>
    } else if (o.__kind__ === "opaque") {
        if (!o.repr) {
            return <span>⟨{o.__class__}⟩</span>
        } else {
            return <span>{o.repr}</span>
        }
    } else if (o.__kind__ === "plotly") {
        const {data, layout} = JSON.parse(o.value)
        // ref: https://github.com/remix-run/remix/discussions/2936
        return <ClientOnly>
            <React.Suspense fallback="loading">
                <Plot data={data} layout={layout} />
            </React.Suspense>
        </ClientOnly>
    } else if (o.__kind__ === "html") {
        const children = o.children.map((c, i) => <Show o={c} depth={depth + 1} key={i} />)
        return React.createElement(o.tag, o.attrs, ...children)
    } else if (o.__kind__ === 'blob') {
        throw "blob visualisations not implemented"
    } else {
        throw "not implemented"
    }
}

function interlace<T>(xs: T[], sep: T): T[] {
    if (xs.length == 0) {
        return xs
    }
    const out = [xs[0]]
    for (let i = 1; i < xs.length; i++) {
        out.push(sep, xs[i])
    }
    return out
}

export function ShowArgs({args} : {args : {[k : string] : VisualObject}}) {
    const keys = Object.getOwnPropertyNames(args)
    if (keys.length === 0) {
        return <span>-</span>
    }
    const cs = keys.map(k => <span key={k}>{k} : <Show o={args[k]} depth={0}/></span>)
    return <span>{cs}</span>
}