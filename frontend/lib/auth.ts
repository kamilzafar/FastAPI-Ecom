"use server";
import { cookies } from 'next/headers';

export const myDeleteCookie = () => {
    cookies().delete("access_token") 
    cookies().delete("refresh_token")
    console.log("cookie deleted");
}

export const myGetCookie = () => {
    const tokens = cookies().get("access_token")?.value || cookies().get("refresh_token")?.value
    return tokens
}

export const checkCookie = () => {
    const cookie = cookies().get("access_token") || cookies().get("refresh_token")
    return cookie
}

export const mySetCookie = (access_token: string, refresh_token: string) => {
    cookies().set({
        name: 'access_token',
        value: access_token,
        httpOnly: true,
        path: '/',
        expires: new Date(Date.now() + 60 * 60 * 1000)
    })
    cookies().set({
        name: 'refresh_token',
        value: refresh_token,
        httpOnly: true,
        path: '/',
        expires: new Date(Date.now() + 60 * 60 * 1000 * 24 * 7)
    })
    console.log("cookie set");
}