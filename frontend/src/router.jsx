import React,{useEffect,useState}from'react'
export function useRoute(){const read=()=>location.hash.replace(/^#/,'')||'/';const[route,setRoute]=useState(read);useEffect(()=>{const h=()=>setRoute(read());addEventListener('hashchange',h);return()=>removeEventListener('hashchange',h)},[]);return route}
export function Link({to,children,className,onClick}){return <a href={`#${to}`} className={className} onClick={onClick}>{children}</a>}
