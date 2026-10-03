import {useEffect} from "react"; export function C({value}){useEffect(()=>{console.log("mounted")},[value]);return null;}
