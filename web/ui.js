var z,Ke,$t,Y,Te,he,Ge,be,Xe,Ee,Pe,Rt,ie=Symbol.for("pv"),xe={},ke=[],At=/^m(i|n|o|s|text|space)$/,De=Array.isArray,Me=ke.slice,te=Object.assign;function ee(n){n&&n.parentNode&&n.remove()}function Ye(n,t,a){var s,l,o,p={},c=arguments.length;for(o in t)o=="key"?s=t[o]:o=="ref"&&typeof n!="function"?l=t[o]:p[o]=t[o];return c>2&&(p.children=c>3?Me.call(arguments,2):a),re(n,p,s,l,null)}function re(n,t,a,s,l){var o={type:n,props:t,key:a,ref:s,__k:null,__:null,__b:0,__e:null,__c:null,constructor:ie,__v:l||++Ke,__i:-1,__u:0};return!l&&z.vnode&&z.vnode(o),o}function B(n){return n.children}function me(n,t){this.props=n,this.context=t,this.__g=0}function Q(n,t){if(t==null)return n.__&&Q(n.__,n.__i+1);for(var a;t<n.__k.length;t++)if((a=n.__k[t])&&a.__e)return a.__e;return typeof n.type!="function"||n.props.__P?null:Q(n)}function It(n){var t,a=n.__v,s=a.__e,l=[],o=[],p=n.__P;p&&((t=te({constructor:ie},a)).__v=a.__v+1,z.vnode&&z.vnode(t),$e(p,t,a,n.__n,p.namespaceURI,32&a.__u?[s]:null,l,s||Q(a),32&a.__u,o),t.__v=a.__v,t.__.__k[t.__i]=t,at(l,t,o),a.__=a.__e=null,t.__e!=s&&Qe(t))}function Qe(n){if((n=n.__)&&n.__c&&!n.props.__P)return n.__e=null,n.__k.some(function(t){return t&&(n.__e=t.__e)}),Qe(n)}function qe(n){(8&n.__g||(n.__g|=8,Y.push(n),he++))&&Te==z.debounceRendering||((Te=z.debounceRendering)||queueMicrotask)(Ze)}function Ze(){try{for(var n,t=1;Y.length;)Y.length>t&&Y.sort(Ge),n=Y.shift(),t=Y.length,8&n.__g&&It(n)}finally{(he=Y.length)&&(Te||queueMicrotask)(Ze)}}function et(n,t,a,s,l,o,p,c,g,b,d){var P,h,i,x,A,k,f=s.__k||ke,m=t.length;for(g=Lt(a,t,f,g,m),P=0;P<m;P++)(i=a.__k[P])!=null&&(h=~i.__i&&f[i.__i]||xe,i.__i=P,k=$e(n,i,h,l,o,p,c,g,b,d),x=i.__e,(h.ref!=i.ref||8&h.__u)&&(h.ref&&Re(h.ref,null,i,h),i.ref&&d.push(i.ref,i.__c||x,i)),A=A||x,4&i.__u?(g=tt(i,g,n,!h.__v),h.__e&&(h.__e=null)):typeof i.type=="function"&&k!==void 0?g=k:x&&(g=x.nextSibling),i.__u&=-21);return a.__e=A,g}function Lt(n,t,a,s,l){var o,p,c,g,b,d,P,h,i,x=a.length,A=x,k=0,f=0,m=n.__k=Array(l);for(o=0;o<l;o++)(p=t[o])!=null&&typeof p!="boolean"&&typeof p!="function"?(typeof p!="object"||p.constructor===String?p=m[o]=re(null,p):De(p)?p=m[o]=re(B,{children:p}):p.constructor===ie&&p.__b?p=m[o]=re(p.type,p.props,p.key,p.ref,p.__v):m[o]=p,g=o+k,p.__=n,p.__b=n.__b+1,c=null,~(b=p.__i=zt(p,a,g,A))&&(A--,(c=a[b])&&(c.__u|=2)),c&&c.__v?(p.__u|=16,b==g-1?k--:b==g+1?k++:b!=g&&(b>g?k--:k++,f=1)):(~b||(l>x?k--:l<x&&k++),typeof p.type!="function"&&(p.__u|=4))):m[o]=null;if(f){for(d=[],P=[],o=0;o<l;o++)if((p=m[o])&&16&p.__u){for(k=0,h=d.length;k<h;)d[i=k+h>>1]<p.__i?k=i+1:h=i;d[k]=p.__i,P[o]=k+1}for(k=d.length;o--;)P[o]&&(P[o]==k?k--:m[o].__u|=4)}if(A)for(o=0;o<x;o++)!(c=a[o])||2&c.__u||(c.__e==s&&(s=Q(c)),Ae(c,c));return s}function tt(n,t,a,s){var l,o,p,c;if(typeof n.type=="function"){if(n.props.__P)return t;if(l=n.__k)for(o=0;o<l.length;o++)l[o]&&(l[o].__=n,t=tt(l[o],t,a,!1));return t}for(t&&!t.parentNode&&(t=Q(n))&&!t.parentNode&&(t=null),p=n.__e,c=t;c&&c.nodeType==8;)c=c.nextSibling;for(p!=c&&(!s&&a.moveBefore&&p.parentNode?a.moveBefore(p,t):a.insertBefore(p,t||null)),t=p;(t=t&&t.nextSibling)&&t.nodeType==8&&!t.data.startsWith("$s"););return t}function zt(n,t,a,s){var l,o=n.key,p=n.type,c=t[a],g=c&&!(2&c.__u);if(c===null&&o==null||g&&o==c.key&&p==c.type)return a;if(s>(g?1:0)){for(l=a-1;l>=0;l--)if((c=t[l])&&!(2&c.__u)&&o==c.key&&p==c.type)return l;for(l=a+1;l<t.length;l++)if((c=t[l])&&!(2&c.__u)&&o==c.key&&p==c.type)return l}return-1}function Ve(n,t,a){a==null&&(a=""),t[0]=="-"?n.setProperty(t,a):n[t]=a}function fe(n,t,a,s,l){var o,p;if(t=="style")if(typeof a=="string")n.style.cssText=a;else{if(typeof s=="string"&&(n.style.cssText=s=""),s)for(t in s)a&&t in a||Ve(n.style,t);if(a)for(t in a)s&&a[t]==s[t]||Ve(n.style,t,a[t])}else if(t[0]=="o"&&t[1]=="n")typeof a!="function"&&(a=null),typeof s!="function"&&(s=null),(n.__e||(n.__e={}))[t]=a,a&&s||(p=Pe[t]||(Pe[t]=jt(t)),(n.__a||(n.__a={}))[t]=Ee,o=t!=(t=t.replace(Xe,"$1")),(t=t.slice(2))[0]<"a"&&(t=t.toLowerCase()),a?n.addEventListener(t,p,o):n.removeEventListener(t,p,o));else{if(l=="http://www.w3.org/2000/svg")t=t.replace(/xlink(H|:h)/,"h").replace(/sName$/,"s");else if(t!="width"&&t!="height"&&t!="href"&&t!="list"&&t!="form"&&t!="tabIndex"&&t!="download"&&t!="rowSpan"&&t!="colSpan"&&t!="role"&&t!="popover"&&t in n)try{return void(n[t]=a??"")}catch{}if(typeof a=="function")return;a==null||a===!1&&t[4]!="-"?n.removeAttribute(t):n.setAttribute(t,t=="popover"&&a==1?"":a)}}function jt(n){return function(t){var a=this.__e;if(a){if(a=a[n],t[be]==null)t[be]=Ee++;else if(t[be]<this.__a[n])return;return a(z.event?z.event(t):t)}}}function $e(n,t,a,s,l,o,p,c,g,b){var d,P,h,i,x,A,k,f,m,w,u,D,S,E,W,r,M,T,L=t.type;if(t.constructor!==ie)return null;128&a.__u&&(g=32&a.__u,d=a.__c.__z)&&(t.__u|=g,P=o=[],d.nodeType==8?c=ye(d,o):o.push(d),c=o[0]||c),(d=z.__b)&&d(t);e:if(typeof L=="function"){h=p.length;try{if(f=t.props,m=(d=L.prototype)&&d.render,w=(d=L.contextType)&&s[d.__c],u=d?w?w.props.value:d.__:s,(i=a.__c)?(t.__c=i,2&i.__g&&(i.__g|=1)):(m?t.__c=i=new L(f,u):(t.__c=i=new me(f,u),i.constructor=L,i.render=Wt),w&&w.sub(i),i.state||(i.state={}),i.__n=s,i.__g|=8,i.__h=[],i.__k=[]),m&&(i.__s||(i.__s=i.state),L.getDerivedStateFromProps&&(i.__s==i.state&&(i.__s=te({},i.__s)),te(i.__s,L.getDerivedStateFromProps(f,i.__s)))),x=i.props,A=i.state,i.__v=t,a.__c){if(f!==x&&m&&!L.getDerivedStateFromProps&&i.componentWillReceiveProps&&i.componentWillReceiveProps(f,u),t.__v==a.__v&&!(8&i.__g)||!(4&i.__g)&&i.shouldComponentUpdate&&i.shouldComponentUpdate(f,i.__s,u)===!1){t.__v!=a.__v&&(i.props=f,i.state=i.__s,i.__g&=-9),t.__e=a.__e,t.__k=a.__k,t.__k.some(function(F){F&&(F.__=t)}),ke.push.apply(i.__h,i.__k),i.__k=[],i.__h.length&&p.push(i),c=Q(a);break e}i.componentWillUpdate&&i.componentWillUpdate(f,i.__s,u),m&&i.componentDidUpdate&&i.__h.push(function(){i.componentDidUpdate(x,A,k)})}else m&&!L.getDerivedStateFromProps&&i.componentWillMount&&i.componentWillMount(),m&&i.componentDidMount&&i.__h.push(i.componentDidMount);i.context=u,i.props=f,i.__P=n,i.__g&=-5,D=z.__r,S=m?25:0;do i.__g&=-9,D&&D(t),d=i.render(i.props,i.state=i.__s,i.context);while(8&i.__g&&++S<25);m&&(ke.push.apply(i.__h,i.__k),i.__k=[]),i.state=i.__s,i.getChildContext&&(s=te({},s,i.getChildContext())),m&&a.__c&&i.getSnapshotBeforeUpdate&&(k=i.getSnapshotBeforeUpdate(x,A)),E=d&&d.type===B&&d.key==null?d.props.children:d,f.__P&&(d=c,l=(n=f.__P).namespaceURI,g=o=null,a.props&&a.props.__P!=n&&(a.__k.some(function(F){F&&Ae(F,F)}),a.__k=null),c=a.__k?Q(a,0):null),c=et(n,De(E)?E:[E],t,a,s,l,o,p,c,g,b),f.__P&&(t.__e=null,c=d),t.__u&=-161,P&&P.some(ee),i.__h.length&&p.push(i),1&i.__g&&(i.__g&=-4)}catch(F){if(p.length=h,t.__v=null,g||o)if(F&&F.then){if(t.__u|=128|g,o){for(~(M=o.indexOf(c||void 0))||(M=o.length);(T=o[M-1])&&T.nodeType==8;)M--;for(;M<o.length;M++)if(T=o[M])if(o[M]=null,W){if(T==r)break}else{if(T.nodeType!=8)break;T.data.startsWith("$s")&&(r=ye(W=T))}}if(!W){for(;c&&c.nodeType==8&&c.nextSibling;)c=c.nextSibling;W=c}(d=ye(W=t.__c.__z||(t.__c.__z=W)))?(t.__e=W,c=d):t.__e=c,c=c&&c.nextSibling}else o&&o.some(ee);else t.__e=a.__e;t.__k||(t.__k=a.__k||[]),F&&F.then||nt(t),z.__e(F,t,a)}}else c=t.__e=Ot(a.__e,t,a,s,l,o,p,g,b,n);return(d=z.diffed)&&d(t),c}function ye(n,t){if(n&&n.nodeType==8&&n.data.startsWith("$s"))for(var a=1;n=n.nextSibling;){if(n.nodeType==8){if(n.data.startsWith("$s"))a++;else if(n.data.startsWith("/$s")&&!--a)return n}t&&t.push(n)}}function nt(n){n&&(n.__c&&(n.__c.__g|=4),n.__k&&n.__k.some(nt))}function at(n,t,a){for(var s=0;s<a.length;)Re(a[s++],a[s++],a[s++]);z.__c&&z.__c(t,n),n.some(function(l){try{n=l.__h,l.__h=[],n.some(function(o){o.call(l)})}catch(o){z.__e(o,l.__v)}})}function Ot(n,t,a,s,l,o,p,c,g,b){var d,P,h,i,x,A,k,f,m=a.props||xe,w=t.props,u=t.type;if(u=="svg"?l="http://www.w3.org/2000/svg":u=="math"?l="http://www.w3.org/1998/Math/MathML":l||(l="http://www.w3.org/1999/xhtml"),o){for(d=0;d<o.length;d++)if((x=o[d])&&(u?x.localName==u:x.nodeType==3)){n=x,o[d]=null;break}}if(!n){if(f=b.ownerDocument||document,!u)return f.createTextNode(w);n=f.createElementNS(l,u,w.is?w:b),c&&(z.__m&&z.__m(t,o),c=!1),o=null}if(u){if(b=u=="template"&&n.content||n,o=u=="textarea"&&w.defaultValue!=null?null:o&&Me.call(b.childNodes),!c&&o)for(m={},d=0;d<n.attributes.length;d++)m[(x=n.attributes[d]).name]=x.value;for(d in m)x=m[d],d=="dangerouslySetInnerHTML"?h=x:d=="children"||d in w||d=="value"&&"defaultValue"in w||d=="checked"&&"defaultChecked"in w||fe(n,d,null,x,l);for(d in w)x=w[d],d=="children"?i=x:d=="dangerouslySetInnerHTML"?P=x:d=="value"?A=x:d=="checked"?k=x:c&&typeof x!="function"||m[d]===x||fe(n,d,x,m[d],l);P?(c||h&&(P.__html==h.__html||P.__html==n.innerHTML)||(n.innerHTML=P.__html),t.__k=[]):(h&&(n.textContent=""),(u=="foreignObject"||l=="http://www.w3.org/1998/Math/MathML"&&At.test(u))&&(l="http://www.w3.org/1999/xhtml"),et(b,De(i)?i:[i],t,a,s,l,o,p,o?o[0]:a.__k&&Q(a,0),c,g),o&&o.some(ee)),c&&u!="textarea"||(d="value",u=="progress"&&A==null?n.removeAttribute(d):A==null||A===n[d]&&(u!="progress"||A)||fe(n,d,A,m[d],l),d="checked",k!=null&&k!=n[d]&&fe(n,d,k,m[d],l))}else m===w||c&&n.data==w||(n.data=w);return n}function Re(n,t,a,s){try{typeof n=="function"?t?t.__x=n(t)||1:s&&(s=s.__c||s.__e)&&(t=s.__x)&&(s.__x=null,typeof t=="function"?t():n(null)):n.current=t}catch(l){z.__e(l,a)}}function Ae(n,t,a){var s,l,o,p;if(z.unmount&&z.unmount(n),!(s=n.ref)||s.current&&s.current!=n.__e||Re(s,null,t,n),s=n.__c){if(s.componentWillUnmount)try{s.componentWillUnmount()}catch(c){z.__e(c,t)}s.__P=s.__n=null}if(s=n.__k)for(p=0;p<s.length;p++)s[p]&&Ae(s[p],t,typeof n.type!="function"||a&&!n.props.__P);!a&&(s=n.__c)&&(s=s.__z)&&(l=ye(s,o=[]))&&(s==n.__e&&o.some(ee),ee(l),ee(s)),a||ee(n.__e),n.__e=n.__c=n.__=null}function Wt(n,t,a){return this.constructor(n,a)}function Ie(n,t){var a,s,l,o;z.__&&z.__(n,t),t.nodeType==9&&(t=t.documentElement),s=(a=n&&32&n.__u)?null:t.__k,t.__k=re(B,{children:[n]}),l=[],o=[],$e(t,t.__k,s||xe,xe,t.namespaceURI,s?null:t.firstChild?Me.call(t.childNodes):null,l,s?s.__e:t.firstChild,a,o),at(l,t.__k,o),t.__k.props.children=null}z={__e:function(n,t,a,s){for(var l,o,p;t=t.__;)if((l=t.__c)&&!(1&l.__g)){l.__g|=4;try{if((p=(o=l.constructor)&&o.getDerivedStateFromError)&&l.setState(o.getDerivedStateFromError(n)),l.componentDidCatch&&(l.componentDidCatch(n,s||{}),p=1),p&&8&l.__g)return void(l.__g|=2)}catch(c){n=c}}throw he=0,n}},Ke=0,$t=function(n){return n!=null&&n.constructor===ie},me.prototype.setState=function(n,t){var a=this.__s;a&&a!=this.state||(a=this.__s=te({},this.state)),typeof n=="function"&&(n=n(te({},a),this.props)),n&&(te(a,n),this.__v&&(t&&this.__k.push(t),qe(this)))},me.prototype.forceUpdate=function(n){this.__v&&(this.__g|=4,n&&this.__h.push(n),qe(this))},me.prototype.render=B,Y=[],he=0,Ge=function(n,t){return n.__v.__b-t.__v.__b},be=Symbol(),Xe=/(PointerCapture)$|Capture$/i,Ee=0,Pe={},Rt=0;var de,U,Le,ot,ze=Object.is,ce=0,_t=[],je=[],H=z,st=H.__b,rt=H.__r,it=H.diffed,lt=H.__c,dt=H.unmount,ct=H.__;function We(n,t){H.__h&&H.__h(U,n,ce||t),ce=0;var a=U.__H||(U.__H={__:[],__h:[]});return n>=a.__.length&&a.__.push({}),a.__[n]}function C(n){return ce=1,Ft(vt,n)}function Ft(n,t,a){var s=We(de++,2);if(s.t=n,!s.__c&&(s.__=[a?a(t):vt(void 0,t),function(o){var p=(s.__N||s.__)[0],c=s.t(p,o);ze(p,c)||(s.__N=[c,s.__[1]],s.__c.setState({}))}],s.__c=U,!U.__f)){U.__f=!0;var l=U.shouldComponentUpdate;U.shouldComponentUpdate=function(o,p,c){var g=this.__H;if(!g)return!0;var b=!1,d=this.props!=o;if(g.__.some(function(h){h.__N&&(b=!0,ze(h.__[0],h.__N[0])||(d=!0))}),l){var P=l.call(this,o,p,c);return b?P||d:P}return!b||d}}return s.__}function N(n,t){var a=We(de++,3);!H.__s&&gt(a.__H,t)&&(a.__P=!0,a.__=n,a.u=t,U.__H.__h.push(a))}function we(n){return ce=5,J(function(){return{current:n}},[])}function J(n,t){var a=We(de++,7);return gt(a.__H,t)&&(a.__=n(),a.__H=t),a.__}function Fe(n,t){return ce=8,J(function(){return n},t)}function Ht(){var n;do{for(;n=je.shift();)try{le(n)}catch(a){H.__e(a,{__:(n=n.__P)&&n.__v})}for(;n=_t.shift();){var t=n.__H;if(n.__P&&t)try{t.__h.some(le),t.__h.some(Oe),t.__h=[]}catch(a){t.__h=[],H.__e(a,n.__v)}}}while(je.length)}H.__b=function(n){U=null,st&&st(n)},H.__=function(n,t){n&&t.__k&&t.__k.__m&&(n.__m=t.__k.__m),ct&&ct(n,t)},H.__r=function(n){rt&&rt(n),de=0;var t=(U=n.__c).__H;t&&(Le==U?U.__h=[]:(t.__h.some(le),t.__h.some(Oe),de=0),t.__h=[],t.__.some(function(a){a.__N&&(a.__=a.__N),a.u=a.__N=void 0})),Le=U},H.diffed=function(n){it&&it(n);var t=n.__c;t&&t.__H&&(t.__H.__h.length&&ut(_t.push(t)),t.__H.__.some(function(a){a.u&&(a.__H=a.u)})),Le=U=null},H.__c=function(n,t){t.some(function(a){try{a.__h.some(le),a.__h=a.__h.filter(function(s){return!s.__||Oe(s)})}catch(s){a.__h=[function(){throw s}]}}),lt&&lt(n,t)},H.unmount=function(n){dt&&dt(n);var t,a,s=n.__c;s&&s.__H&&(s.__H.__.some(function(l){try{if(l.__P&&l.__c){if(a===void 0){for(a=n.__;a&&(!a.__c||!a.__c.__P);)a=a.__;a=a&&a.__c}l.__P=a,ut(je.push(l))}else le(l)}catch(o){t=o}}),s.__H=void 0,t&&H.__e(t,s.__v))};var pt=typeof requestAnimationFrame=="function";function Ut(n){var t,a=function(){clearTimeout(s),pt&&cancelAnimationFrame(t),setTimeout(n)},s=setTimeout(a,35);pt&&(t=requestAnimationFrame(a))}function ut(n){n!=1&&ot==H.requestAnimationFrame||((ot=H.requestAnimationFrame)||Ut)(Ht)}function le(n){var t=U,a=n.__c;typeof a=="function"&&(n.__c=void 0,a()),U=t}function Oe(n){var t=U;n.__c=n.__(),U=t}function gt(n,t){return!n||n.length!=t.length||t.some(function(a,s){return!ze(a,n[s])})}function vt(n,t){return typeof t=="function"?t(n):t}var Nt=Symbol.for("pv"),Bt=0;function e(n,t,a,s,l,o){t||(t={});var p,c,g=t;if("ref"in g&&typeof n!="function")for(c in g={},t)c=="ref"?p=t[c]:g[c]=t[c];var b={type:n,props:g,key:a,ref:p,__k:null,__:null,__b:0,__e:null,__c:null,constructor:Nt,__v:--Bt,__i:-1,__u:0};return(l||o)&&(b.__source=l,b.__self=o),z.vnode&&z.vnode(b),b}function ft(n){let{sdk:t,pendingPackages:a,sandbox:s,sandboxOs:l,onCancel:o,onAllConfirmed:p}=n,[c,g]=C(0),[b,d]=C(null),[P,h]=C({}),[i,x]=C(!0),[A,k]=C(!1),f=a[c];N(()=>{if(!f){p();return}let u=!0;return x(!0),t.api.call("get_env_form",{package:f,reveal:!1,sandbox:s,sandbox_os:l}).then(D=>{if(!u)return;d(D);let S={};for(let E of D.fields)S[E.key]=E.value;h(S)}).catch(D=>{u&&t.notifyToast(`\u041E\u0448\u0438\u0431\u043A\u0430 \u0437\u0430\u0433\u0440\u0443\u0437\u043A\u0438 .env \u0434\u043B\u044F ${f}: ${D.message}`,"error")}).finally(()=>{u&&x(!1)}),()=>{u=!1}},[f,s,l]);let m=b?b.fields.filter(u=>u.required?!(P[u.key]??"").trim()&&!(u.is_secret&&u.has_existing_value):!1):[],w=async()=>{if(!(!f||m.length>0)){k(!0);try{await t.api.call("save_env_preset",{package:f,values:P,apply_system:!1,sandbox:s,sandbox_os:l}),t.notifyToast(`\u041F\u0440\u0435\u0441\u0435\u0442 .env \u0434\u043B\u044F \xAB${f}\xBB \u043F\u043E\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043D`,"success"),c+1>=a.length?p():g(c+1)}catch(u){t.notifyToast(u.message||"\u041E\u0448\u0438\u0431\u043A\u0430 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u0438\u044F \u043F\u0440\u0435\u0441\u0435\u0442\u0430","error")}finally{k(!1)}}};return e("div",{class:"de-eng-backdrop",children:e("div",{class:"de-eng-modal",role:"dialog","aria-modal":"true","aria-label":"\u041F\u043E\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u0438\u0435 .env \u043F\u0435\u0440\u0435\u0434 \u0437\u0430\u043F\u0443\u0441\u043A\u043E\u043C",children:[e("div",{class:"de-eng-modal-hdr",children:[e("div",{children:[e("div",{style:{fontFamily:"var(--de-font-display)",fontSize:"16px",fontWeight:700},children:"\u041F\u043E\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u0438\u0435 .env \u043F\u0435\u0440\u0435\u0434 \u0432\u044B\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u0435\u043C \u043F\u043B\u0430\u043D\u0430"}),e("div",{class:"de-eng-meta de-eng-mono",children:[e("span",{children:["\u0428\u0430\u0433 ",Math.min(c+1,a.length)," \u0438\u0437 ",a.length]}),e("span",{children:"\xB7"}),e("span",{children:["\u041F\u0430\u043A\u0435\u0442: ",f]})]})]}),e("button",{type:"button",class:"de-eng-btn sm",onClick:o,children:"\u041E\u0442\u043C\u0435\u043D\u0430"})]}),e("div",{class:"de-eng-modal-body",children:i||!b?e("div",{style:{color:"var(--de-muted)"},children:"\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0448\u0430\u0431\u043B\u043E\u043D\u0430 .env..."}):e(B,{children:[e("div",{class:"de-eng-meta",children:["\u0417\u0430\u043F\u043E\u043B\u043D\u0438\u0442\u0435 \u043E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u044B\u0435 \u043F\u0430\u0440\u0430\u043C\u0435\u0442\u0440\u044B \u0438\u043B\u0438 \u0443\u043A\u0430\u0436\u0438\u0442\u0435 \u043C\u0430\u0440\u043A\u0435\u0440\u044B ",e("span",{class:"de-eng-mono",children:"#AUTO#"}),","," ",e("span",{class:"de-eng-mono",children:"#GEN#"})," \u0438\u043B\u0438 ",e("span",{class:"de-eng-mono",children:"#SKIP#"}),". \u041F\u0440\u0435\u0441\u0435\u0442 \u0441\u043E\u0445\u0440\u0430\u043D\u044F\u0435\u0442\u0441\u044F \u0441 \u043F\u0440\u0430\u0432\u0430\u043C\u0438 0600 \u0434\u043E \u043D\u0430\u0447\u0430\u043B\u0430 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0438."]}),b.fields.map(u=>{let D=u.required&&!(P[u.key]??"").trim()&&!(u.is_secret&&u.has_existing_value);return e("div",{style:{display:"flex",flexDirection:"column",gap:"4px",paddingBottom:"10px",borderBottom:"1px solid var(--de-border)"},children:[e("div",{style:{display:"flex",alignItems:"center",justifyContent:"space-between",gap:"8px",flexWrap:"wrap"},children:[e("label",{class:"de-eng-mono",style:{fontWeight:600},children:[u.key,u.required&&e("span",{class:D?"de-eng-status-err":"de-eng-status-ok",style:{marginLeft:"6px"},children:D?"\u041E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u043E":"\u0417\u0430\u043F\u043E\u043B\u043D\u0435\u043D\u043E"})]}),e("div",{class:"de-eng-actions",children:[e("button",{type:"button",class:"de-eng-btn xs",onClick:()=>h(S=>({...S,[u.key]:"#AUTO#"})),children:"#AUTO#"}),e("button",{type:"button",class:"de-eng-btn xs",onClick:()=>h(S=>({...S,[u.key]:"#GEN#"})),children:"#GEN#"}),e("button",{type:"button",class:"de-eng-btn xs",onClick:()=>h(S=>({...S,[u.key]:"#SKIP#"})),children:"#SKIP#"})]})]}),(u.prompt_label||u.comment)&&e("div",{style:{fontSize:"12px",color:"var(--de-muted)"},children:u.prompt_label||u.comment}),e("input",{type:u.is_secret?"password":"text",class:"de-eng-input de-eng-mono",placeholder:u.is_secret&&u.has_existing_value?`\u0421\u0435\u043A\u0440\u0435\u0442 \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D (${u.masked_preview})`:u.default||"\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u0437\u043D\u0430\u0447\u0435\u043D\u0438\u0435",value:P[u.key]??"",onInput:S=>h(E=>({...E,[u.key]:S.target.value}))})]},u.key)})]})}),e("div",{class:"de-eng-modal-ftr",children:[e("div",{style:{fontSize:"12px",color:m.length>0?"var(--de-danger)":"var(--de-muted)"},children:m.length>0?`\u041D\u0435 \u0437\u0430\u043F\u043E\u043B\u043D\u0435\u043D\u044B \u043E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u044B\u0435 \u043F\u043E\u043B\u044F: ${m.map(u=>u.key).join(", ")}`:"\u0412\u0441\u0435 \u043E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u044B\u0435 \u043F\u0430\u0440\u0430\u043C\u0435\u0442\u0440\u044B \u0437\u0430\u043F\u043E\u043B\u043D\u0435\u043D\u044B."}),e("div",{class:"de-eng-actions",children:[e("button",{type:"button",class:"de-eng-btn",onClick:o,children:"\u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C \u043F\u043B\u0430\u043D"}),e("button",{type:"button",class:"de-eng-btn primary",disabled:A||i||m.length>0,onClick:w,children:A?"\u0421\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u0438\u0435...":c+1>=a.length?"\u041F\u0440\u0438\u043D\u044F\u0442\u044C .env \u0438 \u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u043F\u043B\u0430\u043D":"\u041F\u0440\u0438\u043D\u044F\u0442\u044C .env \u0438 \u0434\u0430\u043B\u0435\u0435"})]})]})]})})}var Jt={queued:{label:"\u0412 \u043E\u0447\u0435\u0440\u0435\u0434\u0438",cls:""},running:{label:"\u0412\u044B\u043F\u043E\u043B\u043D\u044F\u0435\u0442\u0441\u044F",cls:"de-eng-status-accent"},succeeded:{label:"\u0423\u0441\u043F\u0435\u0448\u043D\u043E",cls:"de-eng-status-ok"},failed:{label:"\u041E\u0448\u0438\u0431\u043A\u0430",cls:"de-eng-status-err"},cancelled:{label:"\u041E\u0442\u043C\u0435\u043D\u0435\u043D\u043E",cls:"de-eng-status-warn"}},qt={live:"\u0411\u043E\u0435\u0432\u043E\u0439",sandbox:"Sandbox",dry_run:"Dry-Run"};function bt(n){let{jobs:t,loading:a,onRefresh:s,onOpenJob:l}=n;return e("div",{class:"de-eng-panel",children:[e("div",{class:"de-eng-panel-title",children:[e("span",{children:"\u0418\u0441\u0442\u043E\u0440\u0438\u044F \u0437\u0430\u043F\u0443\u0441\u043A\u043E\u0432 \u0438 \u0430\u0443\u0434\u0438\u0442 \u043F\u043B\u0430\u043D\u043E\u0432"}),e("button",{type:"button",class:"de-eng-btn sm",disabled:a,onClick:s,children:a?"\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435...":"\u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C \u0441\u043F\u0438\u0441\u043E\u043A"})]}),t.length===0?e("div",{style:{padding:"28px 12px",textAlign:"center",color:"var(--de-muted)"},children:a?"\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0438\u0441\u0442\u043E\u0440\u0438\u0438 \u0437\u0430\u043F\u0443\u0441\u043A\u043E\u0432...":"\u0418\u0441\u0442\u043E\u0440\u0438\u044F \u0437\u0430\u043F\u0443\u0441\u043A\u043E\u0432 \u043F\u043E\u043A\u0430 \u043F\u0443\u0441\u0442\u0430. \u0412\u044B\u043F\u043E\u043B\u043D\u0438\u0442\u0435 \u043B\u044E\u0431\u043E\u0439 \u043F\u043B\u0430\u043D \u0432\u043E \u0432\u043A\u043B\u0430\u0434\u043A\u0435 \xAB\u041E\u0440\u043A\u0435\u0441\u0442\u0440\u0430\u0442\u043E\u0440\xBB."}):e("div",{style:{overflowX:"auto"},children:e("table",{class:"de-eng-table",children:[e("thead",{children:e("tr",{children:[e("th",{children:"\u0414\u0430\u0442\u0430 / ID \u0437\u0430\u0434\u0430\u0447\u0438"}),e("th",{children:"\u0418\u043D\u0438\u0446\u0438\u0430\u0442\u043E\u0440"}),e("th",{children:"\u0420\u0435\u0436\u0438\u043C"}),e("th",{children:"\u041F\u0430\u043A\u0435\u0442\u044B \u0432 \u043F\u043B\u0430\u043D\u0435"}),e("th",{children:"\u0421\u0442\u0430\u0442\u0443\u0441"}),e("th",{style:{textAlign:"right"},children:"\u0414\u043B\u0438\u0442\u0435\u043B\u044C\u043D\u043E\u0441\u0442\u044C"}),e("th",{})]})}),e("tbody",{children:t.map(o=>{let p=Jt[o.status]||{label:o.status,cls:""};return e("tr",{children:[e("td",{class:"de-eng-mono",children:[e("div",{children:o.created_at}),e("div",{style:{color:"var(--de-muted)",fontSize:"11px"},children:o.job_id})]}),e("td",{children:[e("div",{children:o.actor?.username||"\u2014"}),e("div",{style:{color:"var(--de-muted)",fontSize:"11px"},children:o.actor?.role||""})]}),e("td",{class:"de-eng-mono",children:qt[o.mode]||o.mode}),e("td",{class:"de-eng-mono",children:o.ordered_packages.length>0?o.ordered_packages.join(", "):"\u2014"}),e("td",{children:[e("span",{class:p.cls,children:p.label}),o.error&&e("div",{style:{color:"var(--de-danger)",fontSize:"11px",maxWidth:"240px"},children:o.error})]}),e("td",{class:"de-eng-mono",style:{textAlign:"right"},children:o.duration_sec?`${o.duration_sec.toFixed(1)} \u0441`:"\u2014"}),e("td",{style:{textAlign:"right"},children:e("button",{type:"button",class:"de-eng-btn xs",onClick:()=>l(o.job_id),children:"\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u043B\u043E\u0433"})})]},o.job_id)})})]})})]})}var mt={queued:{text:"\u0412 \u043E\u0447\u0435\u0440\u0435\u0434\u0438",cls:""},running:{text:"\u0412\u044B\u043F\u043E\u043B\u043D\u044F\u0435\u0442\u0441\u044F",cls:"de-eng-status-accent"},succeeded:{text:"\u0423\u0441\u043F\u0435\u0448\u043D\u043E",cls:"de-eng-status-ok"},done:{text:"\u0413\u043E\u0442\u043E\u0432\u043E",cls:"de-eng-status-ok"},failed:{text:"\u041E\u0448\u0438\u0431\u043A\u0430",cls:"de-eng-status-err"},cancelled:{text:"\u041E\u0442\u043C\u0435\u043D\u0435\u043D\u043E",cls:"de-eng-status-warn"},skipped:{text:"\u041F\u0440\u043E\u043F\u0443\u0449\u0435\u043D\u043E",cls:""}},Vt={live:"\u0411\u043E\u0435\u0432\u043E\u0439 \u0440\u0435\u0436\u0438\u043C",sandbox:"Sandbox (\u043F\u0435\u0441\u043E\u0447\u043D\u0438\u0446\u0430)",dry_run:"Dry-Run (\u0441\u0438\u043C\u0443\u043B\u044F\u0446\u0438\u044F)"};function yt(n){let{sdk:t,jobId:a,onClose:s,onFinished:l}=n,[o,p]=C(null),[c,g]=C([]),[b,d]=C("__all__"),[P,h]=C(!0),[i,x]=C(!1),[A,k]=C(0),f=we(0),m=we(!1),w=we(null),u=o?o.status==="queued"||o.status==="running":!0;N(()=>{f.current=0,m.current=!1,g([]),p(null),d("__all__")},[a]),N(()=>{let r=!0,M=null,T=async()=>{try{let L=await t.api.call("get_job_status",{job_id:a,offset:f.current});if(!r)return;p(L.job),L.events&&L.events.length>0&&(f.current=L.next_offset,g(q=>q.concat(L.events))),L.job.status==="queued"||L.job.status==="running"?M=setTimeout(T,800):m.current||(m.current=!0,l?.())}catch(L){if(!r)return;t.notifyToast(`\u041E\u0448\u0438\u0431\u043A\u0430 \u043E\u043F\u0440\u043E\u0441\u0430 \u0437\u0430\u0434\u0430\u0447\u0438: ${L.message}`,"error")}};return T(),()=>{r=!1,M&&clearTimeout(M)}},[a]),N(()=>{if(!u)return;let r=Date.now(),M=setInterval(()=>{k(Math.floor((Date.now()-r)/1e3))},1e3);return()=>clearInterval(M)},[u,a]);let D=J(()=>b==="__all__"?c:c.filter(r=>r.pkg===b),[c,b]);N(()=>{P&&w.current&&(w.current.scrollTop=w.current.scrollHeight)},[D,P]);let S=async()=>{if(await t.requestConfirm({title:"\u041E\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C \u0432\u044B\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u0435 \u043F\u043B\u0430\u043D\u0430?",message:"\u0412\u043E\u0440\u043A\u0435\u0440\u0443 \u0431\u0443\u0434\u0435\u0442 \u043E\u0442\u043F\u0440\u0430\u0432\u043B\u0435\u043D \u0441\u0438\u0433\u043D\u0430\u043B SIGINT \u0434\u043B\u044F \u043F\u0440\u0435\u0440\u044B\u0432\u0430\u043D\u0438\u044F \u043E\u043F\u0435\u0440\u0430\u0446\u0438\u0438 \u0438 \u0437\u0430\u043F\u0443\u0441\u043A\u0430 \u0430\u0442\u043E\u043C\u0430\u0440\u043D\u043E\u0433\u043E LIFO-\u043E\u0442\u043A\u0430\u0442\u0430 \u0442\u0440\u0430\u043D\u0437\u0430\u043A\u0446\u0438\u0438.",confirmText:"\u041E\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C \u0438 \u043E\u0442\u043A\u0430\u0442\u0438\u0442\u044C",danger:!0})){x(!0);try{await t.api.call("cancel_job",{job_id:a}),t.notifyToast("\u0417\u0430\u043F\u0440\u043E\u0441 \u043D\u0430 \u043E\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0443 \u0437\u0430\u0434\u0430\u0447\u0438 \u043E\u0442\u043F\u0440\u0430\u0432\u043B\u0435\u043D (SIGINT)","warning")}catch(M){t.notifyToast(`\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043E\u0442\u043C\u0435\u043D\u0438\u0442\u044C \u0437\u0430\u0434\u0430\u0447\u0443: ${M.message}`,"error")}finally{x(!1)}}},E=mt[o?.status||"queued"]||{text:o?.status||"\u2014",cls:""},W=o&&!u?`${o.duration_sec.toFixed(1)} \u0441`:`${String(Math.floor(A/60)).padStart(2,"0")}:${String(A%60).padStart(2,"0")}`;return e("div",{class:"de-eng-backdrop",onClick:r=>{!u&&r.target===r.currentTarget&&s()},children:e("div",{class:"de-eng-modal",role:"dialog","aria-modal":"true","aria-label":`\u041C\u043E\u043D\u0438\u0442\u043E\u0440 \u0437\u0430\u0434\u0430\u0447\u0438 ${a}`,children:[e("div",{class:"de-eng-modal-hdr",children:[e("div",{children:[e("div",{style:{fontFamily:"var(--de-font-display)",fontSize:"16px",fontWeight:700},children:["\u0412\u044B\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u0435 \u043F\u043B\u0430\u043D\u0430 \xB7 ",e("span",{class:"de-eng-mono",children:a})]}),e("div",{class:"de-eng-meta de-eng-mono",children:[e("span",{class:E.cls,children:E.text}),e("span",{children:"\xB7"}),e("span",{children:Vt[o?.mode||"live"]||o?.mode}),e("span",{children:"\xB7"}),e("span",{children:["\u0412\u0440\u0435\u043C\u044F: ",W]}),o?.phase&&e("span",{children:["\xB7 ",o.phase]})]})]}),e("div",{class:"de-eng-actions",children:[u&&t.can("jobs.cancel")&&e("button",{type:"button",class:"de-eng-btn danger sm",disabled:i,onClick:S,children:i?"\u041E\u0442\u043C\u0435\u043D\u0430...":"\u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C \u0437\u0430\u0434\u0430\u0447\u0443 (SIGINT)"}),e("button",{type:"button",class:"de-eng-btn sm",onClick:s,children:u?"\u0421\u0432\u0435\u0440\u043D\u0443\u0442\u044C \u0432 \u0444\u043E\u043D":"\u0417\u0430\u043A\u0440\u044B\u0442\u044C"})]})]}),e("div",{style:{padding:"10px 20px",borderBottom:"1px solid var(--de-border)",background:"var(--de-surface)",display:"flex",justifyContent:"space-between",alignItems:"center",gap:"10px",flexWrap:"wrap"},children:[e("div",{class:"de-eng-seg",style:{overflowX:"auto",maxWidth:"100%"},children:[e("button",{type:"button",class:`de-eng-seg-btn ${b==="__all__"?"active":""}`,onClick:()=>d("__all__"),children:["\u041E\u0431\u0449\u0438\u0439 \u043B\u043E\u0433 (",c.length,")"]}),(o?.ordered_packages||[]).map(r=>{let M=o?.package_statuses?.[r]||"queued",T=mt[M]||{text:M,cls:""};return e("button",{type:"button",class:`de-eng-seg-btn ${b===r?"active":""}`,onClick:()=>d(r),children:[r," \xB7 ",e("span",{class:T.cls,children:T.text})]},r)})]}),e("label",{class:"de-eng-check-row",style:{fontSize:"12px"},children:[e("input",{type:"checkbox",checked:P,onChange:r=>h(r.target.checked)}),e("span",{children:"\u0410\u0432\u0442\u043E\u043F\u0440\u043E\u043A\u0440\u0443\u0442\u043A\u0430"})]})]}),e("div",{class:"de-eng-modal-body",children:[o?.error&&e("div",{style:{padding:"10px 12px",border:"1px solid var(--de-danger)",borderRadius:"var(--de-radius)",color:"var(--de-danger)",fontSize:"13px"},children:o.error}),e("pre",{ref:w,class:"de-eng-log-view",children:D.length===0?u?"\u041E\u0436\u0438\u0434\u0430\u043D\u0438\u0435 \u0432\u044B\u0432\u043E\u0434\u0430 \u043E\u0442 \u0432\u043E\u0440\u043A\u0435\u0440\u0430...":"\u0414\u043B\u044F \u044D\u0442\u043E\u0439 \u0432\u043A\u043B\u0430\u0434\u043A\u0438 \u043D\u0435\u0442 \u0437\u0430\u043F\u0438\u0441\u0435\u0439 \u0436\u0443\u0440\u043D\u0430\u043B\u0430.":D.map((r,M)=>e("div",{style:{color:r.level==="error"?"#fca5a5":r.level==="warning"?"#fcd34d":r.level==="success"?"#86efac":"#e2e8f0"},children:[e("span",{style:{color:"#64748b"},children:["[",r.ts||"--:--:--","]"]}),b==="__all__"&&r.pkg?e("span",{style:{color:"#38bdf8"},children:[" [",r.pkg,"]"]}):null," ",r.line]},M))})]}),e("div",{class:"de-eng-modal-ftr",children:[e("div",{class:"de-eng-meta de-eng-mono",children:["\u0418\u043D\u0438\u0446\u0438\u0430\u0442\u043E\u0440: ",o?.actor?.username||"\u2014"," (",o?.actor?.role||"\u2014",") \xB7 \u0421\u043E\u0437\u0434\u0430\u043D\u0430: ",o?.created_at||"\u2014"]}),e("button",{type:"button",class:"de-eng-btn",onClick:s,children:u?"\u0421\u0432\u0435\u0440\u043D\u0443\u0442\u044C":"\u0413\u043E\u0442\u043E\u0432\u043E"})]})]})})}function ht(n){let{sdk:t,pkg:a,initialTab:s,sandbox:l,sandboxOs:o,onClose:p,onEnvSaved:c}=n,[g,b]=C(s),[d,P]=C(null),[h,i]=C(null),[x,A]=C("inspect"),[k,f]=C(null),[m,w]=C(!1),[u,D]=C(null),[S,E]=C({}),[W,r]=C(!1),[M,T]=C(!1),L=t.can("env.read"),F=t.can("env.write"),q=t.can("env.reveal"),j=t.can("logs.read"),V=t.can("service.control"),ne=t.can("plan.execute");N(()=>{let v=!0;return r(!0),t.api.call("get_package_details",{package:a.key,sandbox:l,sandbox_os:o}).then($=>{v&&P($)}).catch($=>{v&&t.notifyToast(`\u041E\u0448\u0438\u0431\u043A\u0430 \u0437\u0430\u0433\u0440\u0443\u0437\u043A\u0438 \u043A\u0430\u0440\u0442\u043E\u0447\u043A\u0438: ${$.message}`,"error")}).finally(()=>{v&&r(!1)}),()=>{v=!1}},[a.key,l,o]),N(()=>{(g==="install_log"||g==="service_logs")&&j&&!h&&t.api.call("get_package_logs",{package:a.key,sandbox:l,sandbox_os:o}).then(i).catch(v=>t.notifyToast(`\u041E\u0448\u0438\u0431\u043A\u0430 \u0447\u0442\u0435\u043D\u0438\u044F \u043B\u043E\u0433\u043E\u0432: ${v.message}`,"error"))},[g,j]);let Z=async v=>{if(L)try{let $=await t.api.call("inspect_env",{package:a.key,reveal:v,sandbox:l,sandbox_os:o});f($)}catch($){t.notifyToast(`\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044C .env (--show): ${$.message}`,"error")}},pe=async()=>{if(L)try{let v=await t.api.call("get_env_form",{package:a.key,reveal:!1,sandbox:l,sandbox_os:o});D(v);let $={};for(let K of v.fields)$[K.key]=K.value;E($)}catch(v){t.notifyToast(`\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044C \u0444\u043E\u0440\u043C\u0443 .env: ${v.message}`,"error")}};N(()=>{g==="env"&&L&&(Z(m),pe())},[g,m]);let ue=async v=>{if(!(v&&!l&&!await t.requestConfirm({title:"\u041F\u0440\u0438\u043C\u0435\u043D\u0438\u0442\u044C .env \u0432 \u0441\u0438\u0441\u0442\u0435\u043C\u0443?",message:`\u041D\u043E\u0432\u044B\u0435 \u0437\u043D\u0430\u0447\u0435\u043D\u0438\u044F \u0431\u0443\u0434\u0443\u0442 \u0437\u0430\u043F\u0438\u0441\u0430\u043D\u044B \u0432 \u0441\u0438\u0441\u0442\u0435\u043C\u043D\u044B\u0439 \u0444\u0430\u0439\u043B .env \u043F\u0430\u043A\u0435\u0442\u0430 \xAB${a.name}\xBB \u0441 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u0438\u0435\u043C \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044E\u0449\u0438\u0445 \u043A\u043E\u043C\u043C\u0435\u043D\u0442\u0430\u0440\u0438\u0435\u0432.`,confirmText:"\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C \u0438 \u043F\u0440\u0438\u043C\u0435\u043D\u0438\u0442\u044C"}))){r(!0);try{await t.api.call("save_env_preset",{package:a.key,values:S,apply_system:v,sandbox:l,sandbox_os:o}),t.notifyToast(v?"\u041F\u0440\u0435\u0441\u0435\u0442 \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D \u0438 \u043F\u0440\u0438\u043C\u0435\u043D\u0451\u043D \u0432 \u0441\u0438\u0441\u0442\u0435\u043C\u043D\u044B\u0439 .env":"\u041F\u0440\u0435\u0441\u0435\u0442 .env \u0441\u043E\u0445\u0440\u0430\u043D\u0451\u043D","success"),c(),await Z(m),await pe()}catch($){t.notifyToast($.message||"\u041E\u0448\u0438\u0431\u043A\u0430 \u0441\u043E\u0445\u0440\u0430\u043D\u0435\u043D\u0438\u044F .env","error")}finally{r(!1)}}},Se=async()=>{if(await t.requestConfirm({title:`\u041F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u0441\u043B\u0443\u0436\u0431\u0443 ${a.name}?`,message:"\u0421\u043B\u0443\u0436\u0431\u044B systemd/launchd \u0432\u044B\u0431\u0440\u0430\u043D\u043D\u043E\u0433\u043E \u043F\u0430\u043A\u0435\u0442\u0430 \u0431\u0443\u0434\u0443\u0442 \u043F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0449\u0435\u043D\u044B.",confirmText:"\u041F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C",danger:!0})){T(!0);try{let $=await t.api.call("restart_service",{package:a.key,sandbox:l,sandbox_os:o});if(t.notifyToast($.output||"\u0421\u043B\u0443\u0436\u0431\u0430 \u043F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0449\u0435\u043D\u0430","success"),j){let K=await t.api.call("get_package_logs",{package:a.key,sandbox:l,sandbox_os:o});i(K)}}catch($){t.notifyToast(`\u041E\u0448\u0438\u0431\u043A\u0430 \u043F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u043A\u0430: ${$.message}`,"error")}finally{T(!1)}}};return e("div",{class:"de-eng-backdrop",onClick:v=>{v.target===v.currentTarget&&p()},children:e("div",{class:"de-eng-modal",role:"dialog","aria-modal":"true","aria-label":`\u041A\u0430\u0440\u0442\u043E\u0447\u043A\u0430 \u043F\u0430\u043A\u0435\u0442\u0430 ${a.name}`,children:[e("div",{class:"de-eng-modal-hdr",children:[e("div",{children:[e("div",{style:{fontFamily:"var(--de-font-display)",fontSize:"16px",fontWeight:700},children:a.name}),e("div",{class:"de-eng-meta de-eng-mono",children:[e("span",{children:a.category}),e("span",{children:"\xB7"}),e("span",{children:["v",a.installed?a.installed_version:a.available_version]}),a.installed&&a.update_status==="upgrade"&&e("span",{class:"de-eng-status-warn",children:["\xB7 \u0414\u043E\u0441\u0442\u0443\u043F\u043D\u0430 v",a.available_version]})]})]}),e("div",{class:"de-eng-actions",children:[a.has_service&&V&&e("button",{type:"button",class:"de-eng-btn sm",disabled:M,onClick:Se,children:M?"\u041F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u043A...":"\u041F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u0441\u043B\u0443\u0436\u0431\u0443"}),e("button",{type:"button",class:"de-eng-btn sm",onClick:p,children:"\u0417\u0430\u043A\u0440\u044B\u0442\u044C"})]})]}),e("div",{style:{padding:"10px 20px",borderBottom:"1px solid var(--de-border)",background:"var(--de-surface)"},children:e("div",{class:"de-eng-seg",children:[e("button",{type:"button",class:`de-eng-seg-btn ${g==="info"?"active":""}`,onClick:()=>b("info"),children:"\u0418\u043D\u0444\u043E\u0440\u043C\u0430\u0446\u0438\u044F"}),L&&e("button",{type:"button",class:`de-eng-seg-btn ${g==="env"?"active":""}`,onClick:()=>b("env"),children:"\u041A\u043E\u043D\u0444\u0438\u0433\u0443\u0440\u0430\u0446\u0438\u044F (.env)"}),j&&e("button",{type:"button",class:`de-eng-seg-btn ${g==="install_log"?"active":""}`,onClick:()=>b("install_log"),children:"\u041B\u043E\u0433 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0438"}),j&&e("button",{type:"button",class:`de-eng-seg-btn ${g==="service_logs"?"active":""}`,onClick:()=>b("service_logs"),children:"\u041B\u043E\u0433\u0438 \u0441\u043B\u0443\u0436\u0431\u044B"})]})}),e("div",{class:"de-eng-modal-body",children:[g==="info"&&(W&&!d?e("div",{style:{color:"var(--de-muted)"},children:"\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0438\u043D\u0444\u043E\u0440\u043C\u0430\u0446\u0438\u0438 \u043E \u043F\u0430\u043A\u0435\u0442\u0435..."}):d?e(B,{children:[e("div",{style:{display:"grid",gridTemplateColumns:"repeat(auto-fit, minmax(190px, 1fr))",gap:"12px"},children:[e("div",{children:[e("div",{style:{fontSize:"11px",color:"var(--de-muted)"},children:"\u0421\u0442\u0430\u0442\u0443\u0441"}),e("div",{class:d.installed?"de-eng-status-ok":"",children:d.installed?"\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D":"\u041D\u0435 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D"})]}),e("div",{children:[e("div",{style:{fontSize:"11px",color:"var(--de-muted)"},children:"\u0412\u0435\u0440\u0441\u0438\u044F"}),e("div",{class:"de-eng-mono",children:["v",d.version,d.installed&&d.update_status==="upgrade"?` \u2192 v${d.available_version}`:""]})]}),e("div",{children:[e("div",{style:{fontSize:"11px",color:"var(--de-muted)"},children:"\u0414\u0430\u0442\u0430 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0438"}),e("div",{class:"de-eng-mono",children:d.installed_at})]}),e("div",{children:[e("div",{style:{fontSize:"11px",color:"var(--de-muted)"},children:"\u041A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u044F"}),e("div",{children:d.category||"\u043A\u043E\u0440\u0435\u043D\u044C"})]})]}),d.description&&e("div",{style:{color:"var(--de-text-secondary)"},children:d.description}),d.version_history&&d.version_history.length>0&&e("div",{children:[e("div",{style:{fontWeight:600,marginBottom:"6px"},children:"\u0418\u0441\u0442\u043E\u0440\u0438\u044F \u0432\u0435\u0440\u0441\u0438\u0439"}),e("div",{class:"de-eng-meta de-eng-mono",children:d.version_history.map((v,$)=>e("span",{children:[$>0?" \xB7 ":"","v",v.version," (",v.timestamp||"\u2014",")"]},$))})]}),e("div",{children:[e("div",{style:{fontWeight:600,marginBottom:"6px"},children:["\u0421\u0438\u0441\u0442\u0435\u043C\u043D\u044B\u0435 \u043F\u0443\u0442\u0438 (",d.files_count,")"]}),e("table",{class:"de-eng-table",children:[e("thead",{children:e("tr",{children:[e("th",{children:"\u0414\u0438\u0441\u043A"}),e("th",{children:"\u0422\u0438\u043F"}),e("th",{children:"\u041F\u0443\u0442\u044C"}),e("th",{children:"\u041E\u043F\u0438\u0441\u0430\u043D\u0438\u0435"})]})}),e("tbody",{children:d.files.map(v=>e("tr",{children:[e("td",{class:v.exists?"de-eng-status-ok":"de-eng-status-warn",children:v.exists?"\u0415\u0441\u0442\u044C":"\u041D\u0435\u0442"}),e("td",{class:"de-eng-mono",children:v.type}),e("td",{class:"de-eng-mono",children:v.path}),e("td",{style:{color:"var(--de-muted)"},children:v.desc||"\u2014"})]},v.path))})]})]})]}):e("div",{style:{color:"var(--de-muted)"},children:"\u0414\u0430\u043D\u043D\u044B\u0435 \u043E \u043F\u0430\u043A\u0435\u0442\u0435 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u044B."})),g==="env"&&e(B,{children:[e("div",{style:{display:"flex",alignItems:"center",justifyContent:"space-between",gap:"10px",flexWrap:"wrap"},children:[e("div",{class:"de-eng-seg",children:[e("button",{type:"button",class:`de-eng-seg-btn ${x==="inspect"?"active":""}`,onClick:()=>A("inspect"),children:"\u0420\u0430\u0437\u0432\u0435\u0440\u043D\u0443\u0442\u044B\u0435 \u0437\u043D\u0430\u0447\u0435\u043D\u0438\u044F (--show)"}),e("button",{type:"button",class:`de-eng-seg-btn ${x==="edit"?"active":""}`,onClick:()=>A("edit"),children:"\u0420\u0435\u0434\u0430\u043A\u0442\u043E\u0440 \u043F\u0440\u0435\u0441\u0435\u0442\u0430"})]}),x==="inspect"&&q&&e("button",{type:"button",class:"de-eng-btn sm",onClick:()=>w(v=>!v),children:m?"\u0421\u043A\u0440\u044B\u0442\u044C \u0441\u0435\u043A\u0440\u0435\u0442\u044B":"\u041F\u043E\u043A\u0430\u0437\u0430\u0442\u044C \u0441\u0435\u043A\u0440\u0435\u0442\u044B (--reveal)"})]}),x==="inspect"?k?e(B,{children:[e("div",{class:"de-eng-meta de-eng-mono",children:[e("span",{children:["\u0424\u0430\u0439\u043B: ",k.env_file||"(\u043D\u0435 \u0441\u043E\u0437\u0434\u0430\u043D)"]}),k.warning&&e("span",{children:["\xB7 ",k.warning]})]}),e("table",{class:"de-eng-table",children:[e("thead",{children:e("tr",{children:[e("th",{children:"\u041A\u043B\u044E\u0447"}),e("th",{children:"\u0412 .env"}),e("th",{children:"\u0410\u043A\u0442\u0443\u0430\u043B\u044C\u043D\u043E\u0435 \u0437\u043D\u0430\u0447\u0435\u043D\u0438\u0435"}),e("th",{children:"\u0418\u0441\u0442\u043E\u0447\u043D\u0438\u043A"})]})}),e("tbody",{children:Object.entries(k.entries).map(([v,$])=>e("tr",{children:[e("td",{class:"de-eng-mono",style:{fontWeight:600},children:v}),e("td",{class:"de-eng-mono",style:{color:"var(--de-muted)"},children:$.raw||'""'}),e("td",{class:"de-eng-mono",children:$.resolved||'""'}),e("td",{class:"de-eng-mono",children:$.source})]},v))})]})]}):e("div",{style:{color:"var(--de-muted)"},children:"\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0440\u0430\u0437\u0432\u0435\u0440\u043D\u0443\u0442\u043E\u0439 \u043A\u043E\u043D\u0444\u0438\u0433\u0443\u0440\u0430\u0446\u0438\u0438..."}):u&&u.has_env?e("div",{style:{display:"flex",flexDirection:"column",gap:"12px"},children:[e("div",{class:"de-eng-meta de-eng-mono",children:[e("span",{children:["\u041F\u0440\u0435\u0441\u0435\u0442: ",u.preset_path]}),e("span",{children:"\xB7"}),e("span",{children:u.preset_exists?"\u0421\u043E\u0445\u0440\u0430\u043D\u0451\u043D":"\u0415\u0449\u0451 \u043D\u0435 \u0441\u043E\u0437\u0434\u0430\u043D"})]}),u.fields.map(v=>e("div",{style:{display:"flex",flexDirection:"column",gap:"4px",paddingBottom:"10px",borderBottom:"1px solid var(--de-border)"},children:[e("div",{style:{display:"flex",alignItems:"center",justifyContent:"space-between",gap:"8px",flexWrap:"wrap"},children:[e("label",{class:"de-eng-mono",style:{fontWeight:600},children:[v.key,v.required&&e("span",{class:"de-eng-status-err",style:{marginLeft:"6px"},children:"\u041E\u0431\u044F\u0437\u0430\u0442\u0435\u043B\u044C\u043D\u043E"}),v.is_secret&&e("span",{style:{marginLeft:"6px",color:"var(--de-muted)",fontWeight:400},children:"\xB7 \u0441\u0435\u043A\u0440\u0435\u0442"})]}),F&&e("div",{class:"de-eng-actions",children:[e("button",{type:"button",class:"de-eng-btn xs",onClick:()=>E($=>({...$,[v.key]:"#AUTO#"})),children:"#AUTO#"}),e("button",{type:"button",class:"de-eng-btn xs",onClick:()=>E($=>({...$,[v.key]:"#GEN#"})),children:"#GEN#"}),e("button",{type:"button",class:"de-eng-btn xs",onClick:()=>E($=>({...$,[v.key]:"#SKIP#"})),children:"#SKIP#"})]})]}),(v.prompt_label||v.comment)&&e("div",{style:{fontSize:"12px",color:"var(--de-muted)"},children:v.prompt_label||v.comment}),e("input",{type:v.is_secret?"password":"text",class:"de-eng-input de-eng-mono",disabled:!F,placeholder:v.is_secret&&v.has_existing_value?`\u0422\u0435\u043A\u0443\u0449\u0435\u0435 \u0437\u043D\u0430\u0447\u0435\u043D\u0438\u0435 \u0441\u043A\u0440\u044B\u0442\u043E (${v.masked_preview}) \u2014 \u043E\u0441\u0442\u0430\u0432\u044C\u0442\u0435 \u043F\u0443\u0441\u0442\u044B\u043C, \u0447\u0442\u043E\u0431\u044B \u043D\u0435 \u043C\u0435\u043D\u044F\u0442\u044C`:v.default||"\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u0437\u043D\u0430\u0447\u0435\u043D\u0438\u0435",value:S[v.key]??"",onInput:$=>E(K=>({...K,[v.key]:$.target.value}))})]},v.key)),F&&e("div",{class:"de-eng-actions",style:{justifyContent:"flex-end"},children:[e("button",{type:"button",class:"de-eng-btn",disabled:W,onClick:()=>ue(!1),children:"\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C \u043F\u0440\u0435\u0441\u0435\u0442"}),(a.installed||l)&&(ne||l)&&e("button",{type:"button",class:"de-eng-btn primary",disabled:W,onClick:()=>ue(!0),children:"\u0421\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C \u0438 \u043F\u0440\u0438\u043C\u0435\u043D\u0438\u0442\u044C \u0432 \u0441\u0438\u0441\u0442\u0435\u043C\u043D\u044B\u0439 .env"})]})]}):e("div",{style:{color:"var(--de-muted)"},children:"\u0423 \u044D\u0442\u043E\u0433\u043E \u043F\u0430\u043A\u0435\u0442\u0430 \u043D\u0435\u0442 \u0448\u0430\u0431\u043B\u043E\u043D\u0430 .env."})]}),g==="install_log"&&e("pre",{class:"de-eng-log-view",children:h?h.install_log:"\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u043B\u043E\u0433\u0430 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0438..."}),g==="service_logs"&&e("pre",{class:"de-eng-log-view",children:h?h.service_logs:"\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u043B\u043E\u0433\u043E\u0432 \u0441\u043B\u0443\u0436\u0431\u044B..."})]})]})})}var Kt={web:"Web",file:"\u0424\u0430\u0439\u043B\u044B",script:"\u0421\u043A\u0440\u0438\u043F\u0442",unit:"\u0421\u043B\u0443\u0436\u0431\u0430",service:"\u0421\u043B\u0443\u0436\u0431\u0430",timer:"\u0422\u0430\u0439\u043C\u0435\u0440",env:"ENV",data:"\u0414\u0430\u043D\u043D\u044B\u0435",symlink:"\u0421\u0438\u043C\u043B\u0438\u043D\u043A"};function xt(n){let{packages:t,categories:a,search:s,onSearchChange:l,filter:o,onFilterChange:p,expandedKeys:c,onToggleExpand:g,actions:b,unitUpdates:d,backups:P,restores:h,onSetAction:i,onToggleUnit:x,onToggleBackup:A,onSetRestore:k,onOpenDetails:f}=n,m=J(()=>{let u=s.trim().toLowerCase(),D=new Map;for(let S of t){let E=!!(b[S.key]||d[S.key]&&d[S.key].length>0||P.includes(S.name)||h[S.name]);if(o==="installed"&&!S.installed||o==="planned"&&!E||o==="updates"&&S.update_status!=="upgrade"||u&&!`${S.key} ${S.name} ${S.desc} ${S.category}`.toLowerCase().includes(u))continue;let W=S.category||"\u043A\u043E\u0440\u0435\u043D\u044C";D.has(W)||D.set(W,[]),D.get(W).push(S)}return Array.from(D.entries()).sort(([S],[E])=>S.localeCompare(E,"ru"))},[t,s,o,b,d,P,h]),w=J(()=>{let u=0,D=0,S=0;for(let E of t)E.installed&&u++,E.update_status==="upgrade"&&D++,(b[E.key]||(d[E.key]?.length??0)>0||P.includes(E.name)||h[E.name])&&S++;return{total:t.length,installed:u,updates:D,planned:S}},[t,b,d,P,h]);return e("div",{class:"de-eng-panel",children:[e("div",{class:"de-eng-panel-title",children:[e("span",{children:"\u0414\u0435\u0440\u0435\u0432\u043E \u043F\u0430\u043A\u0435\u0442\u043E\u0432 \u0438 \u044E\u043D\u0438\u0442\u043E\u0432"}),e("span",{class:"de-eng-meta de-eng-mono",children:["\u0412\u0441\u0435\u0433\u043E ",w.total," \xB7 \u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u043E ",w.installed," \xB7 \u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0439 ",w.updates]})]}),e("div",{style:{display:"flex",gap:"10px",flexWrap:"wrap",alignItems:"center"},children:[e("input",{type:"search",class:"de-eng-input",style:{flex:"1 1 200px"},placeholder:"\u041F\u043E\u0438\u0441\u043A \u043F\u043E \u0438\u043C\u0435\u043D\u0438, \u043A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u0438 \u0438\u043B\u0438 \u043E\u043F\u0438\u0441\u0430\u043D\u0438\u044E...",value:s,onInput:u=>l(u.target.value)}),e("div",{class:"de-eng-seg",role:"tablist","aria-label":"\u0424\u0438\u043B\u044C\u0442\u0440 \u043F\u0430\u043A\u0435\u0442\u043E\u0432",children:[["all",`\u0412\u0441\u0435 (${w.total})`],["installed",`\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u043D\u044B\u0435 (${w.installed})`],["planned",`\u0421 \u043F\u043B\u0430\u043D\u043E\u043C (${w.planned})`],["updates",`\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u044F (${w.updates})`]].map(([u,D])=>e("button",{type:"button",class:`de-eng-seg-btn ${o===u?"active":""}`,onClick:()=>p(u),children:D},u))})]}),e("div",{class:"de-eng-tree-scroll",children:m.length===0?e("div",{style:{padding:"24px 12px",textAlign:"center",color:"var(--de-muted)"},children:"\u041F\u0430\u043A\u0435\u0442\u044B \u043F\u043E \u0442\u0435\u043A\u0443\u0449\u0435\u043C\u0443 \u0444\u0438\u043B\u044C\u0442\u0440\u0443 \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u044B. \u041F\u043E\u043F\u0440\u043E\u0431\u0443\u0439\u0442\u0435 \u043E\u0447\u0438\u0441\u0442\u0438\u0442\u044C \u043F\u043E\u0438\u0441\u043A \u0438\u043B\u0438 \u0432\u044B\u043F\u043E\u043B\u043D\u0438\u0442\u044C \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435 \u0431\u0430\u0437\u044B \u043F\u0430\u043A\u0435\u0442\u043E\u0432."}):m.map(([u,D])=>{let S=`cat:${u}`,E=c.has(S),W=a[u]||"";return e("div",{children:[e("div",{class:"de-eng-cat-hdr",role:"button",tabIndex:0,onClick:()=>g(S),onKeyDown:r=>{(r.key==="Enter"||r.key===" ")&&(r.preventDefault(),g(S))},children:[e("span",{children:[e("span",{class:"de-eng-mono",style:{marginRight:"8px",color:"var(--de-muted)"},children:E?"\u25BC":"\u25B6"}),u,W?e("span",{style:{fontWeight:400,color:"var(--de-muted)",marginLeft:"8px",fontSize:"12px"},children:["\u2014 ",W]}):null]}),e("span",{class:"de-eng-mono",style:{fontSize:"12px",color:"var(--de-muted)"},children:D.length})]}),E&&e("div",{style:{paddingLeft:"6px"},children:D.map(r=>{let M=c.has(r.key),T=b[r.key]||null,L=d[r.key]||[],F=P.includes(r.name),q=h[r.name]||"";return e("div",{class:"de-eng-pkg-row",style:{opacity:r.compatible?1:.55},children:[e("div",{class:"de-eng-pkg-main",children:[e("div",{class:"de-eng-pkg-left",children:[e("button",{type:"button",class:"de-eng-expand-btn",title:M?"\u0421\u0432\u0435\u0440\u043D\u0443\u0442\u044C \u044E\u043D\u0438\u0442\u044B \u0438 \u0431\u044D\u043A\u0430\u043F\u044B":"\u0420\u0430\u0441\u043A\u0440\u044B\u0442\u044C \u044E\u043D\u0438\u0442\u044B \u0438 \u0431\u044D\u043A\u0430\u043F\u044B",onClick:()=>g(r.key),children:M?"\u2212":"+"}),e("div",{style:{minWidth:0},children:[e("div",{style:{display:"flex",alignItems:"center",gap:"8px",flexWrap:"wrap"},children:[e("button",{type:"button",class:"de-eng-pkg-name",onClick:()=>f(r,"info"),children:r.name}),e("span",{class:"de-eng-meta de-eng-mono",children:[r.installed?r.update_status==="upgrade"?e("span",{class:"de-eng-status-warn",children:["v",r.installed_version," \u2192 v",r.available_version]}):e("span",{class:"de-eng-status-ok",children:["\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D \xB7 v",r.installed_version]}):e("span",{children:["v",r.available_version]}),!r.compatible&&e("span",{class:"de-eng-status-err",children:"\xB7 \u041D\u0435\u0441\u043E\u0432\u043C\u0435\u0441\u0442\u0438\u043C"}),r.is_external&&e("span",{children:"\xB7 \u0412\u043D\u0435\u0448\u043D\u0438\u0439"}),!r.manifest_available&&e("span",{class:"de-eng-status-warn",children:"\xB7 \u041C\u0430\u043D\u0438\u0444\u0435\u0441\u0442 \u0443\u0434\u0430\u043B\u0451\u043D"}),L.length>0&&e("span",{class:"de-eng-status-accent",children:["\xB7 \u042E\u043D\u0438\u0442\u044B: ",L.join(", ")]})]})]}),r.desc&&e("div",{style:{fontSize:"12px",color:"var(--de-muted)",marginTop:"2px"},children:r.desc})]})]}),e("div",{class:"de-eng-actions",children:[r.has_env&&e("button",{type:"button",class:"de-eng-btn xs",title:"\u041F\u0440\u043E\u0441\u043C\u043E\u0442\u0440 \u0438 \u0440\u0435\u0434\u0430\u043A\u0442\u0438\u0440\u043E\u0432\u0430\u043D\u0438\u0435 .env",onClick:()=>f(r,"env"),children:r.has_preset?".env (\u043F\u0440\u0435\u0441\u0435\u0442)":".env"}),r.installed?e(B,{children:[e("button",{type:"button",class:`de-eng-btn xs ${T==="reinstall"?"primary":""}`,disabled:!r.compatible||!r.manifest_available,onClick:()=>i(r.key,T==="reinstall"?null:"reinstall"),children:T==="reinstall"?r.update_status==="upgrade"?"\u2713 \u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C":"\u2713 \u041F\u0435\u0440\u0435\u0443\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C":r.update_status==="upgrade"?"\u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C":"\u041F\u0435\u0440\u0435\u0443\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C"}),e("button",{type:"button",class:`de-eng-btn xs ${T==="uninstall"?"danger":""}`,onClick:()=>i(r.key,T==="uninstall"?null:"uninstall"),children:T==="uninstall"?"\u2713 \u0423\u0434\u0430\u043B\u0438\u0442\u044C":"\u0423\u0434\u0430\u043B\u0438\u0442\u044C"})]}):e("button",{type:"button",class:`de-eng-btn xs ${T==="install"?"primary":""}`,disabled:!r.compatible||!r.manifest_available,onClick:()=>i(r.key,T==="install"?null:"install"),children:T==="install"?"\u2713 \u0423\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C":"\u0423\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C"})]})]}),M&&e("div",{class:"de-eng-units-box",children:[r.units.length>0&&e(B,{children:[e("div",{style:{fontSize:"11px",color:"var(--de-muted)",fontWeight:600},children:["\u042E\u043D\u0438\u0442\u044B \u043F\u0430\u043A\u0435\u0442\u0430 ",r.installed?"(\u043E\u0442\u043C\u0435\u0442\u044C\u0442\u0435 \u0434\u043B\u044F \u0442\u043E\u0447\u0435\u0447\u043D\u043E\u0433\u043E \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u044F)":""]}),r.units.map(j=>{let V=L.includes(j.name),ne=r.installed&&r.compatible&&r.manifest_available&&j.type!=="data";return e("div",{class:"de-eng-unit-row",children:[e("label",{class:"de-eng-check-row",style:{fontSize:"12px"},children:[ne&&e("input",{type:"checkbox",checked:V,onChange:()=>x(r.key,j.name)}),e("span",{class:"de-eng-mono",style:{color:"var(--de-accent)",minWidth:"58px"},children:Kt[j.type]||j.type}),e("span",{class:"de-eng-mono",style:{fontWeight:500},children:j.name}),j.dest&&e("span",{class:"de-eng-mono",style:{color:"var(--de-muted)"},children:["\u2192 ",j.dest]})]}),j.type==="env"&&e("button",{type:"button",class:"de-eng-btn xs",onClick:()=>f(r,"env"),children:"\u041E\u0442\u043A\u0440\u044B\u0442\u044C .env"})]},j.name)})]}),r.installed&&e("div",{style:{display:"flex",alignItems:"center",gap:"12px",flexWrap:"wrap",paddingTop:"4px"},children:[e("label",{class:"de-eng-check-row",style:{fontSize:"12px"},children:[e("input",{type:"checkbox",checked:F,onChange:()=>A(r.name)}),e("span",{children:"\u0421\u043E\u0437\u0434\u0430\u0442\u044C \u0431\u044D\u043A\u0430\u043F \u043F\u0435\u0440\u0435\u0434 \u0432\u044B\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u0435\u043C"})]}),r.backups.length>0&&e("div",{style:{display:"flex",alignItems:"center",gap:"6px"},children:[e("span",{style:{fontSize:"12px",color:"var(--de-muted)"},children:"\u0412\u043E\u0441\u0441\u0442\u0430\u043D\u043E\u0432\u0438\u0442\u044C:"}),e("select",{class:"de-eng-select",style:{width:"auto",padding:"3px 8px",fontSize:"12px"},value:q,onChange:j=>k(r.name,j.target.value),children:[e("option",{value:"",children:"\u041D\u0435 \u0432\u043E\u0441\u0441\u0442\u0430\u043D\u0430\u0432\u043B\u0438\u0432\u0430\u0442\u044C"}),r.backups.map((j,V)=>e("option",{value:j.filename,children:["#",V+1," \xB7 ",j.timestamp," (",j.size_human,")",j.comment?` \u2014 ${j.comment}`:""]},j.filename))]})]})]})]})]},r.key)})})]},u)})})]})}var kt=`
.de-eng-root {
  display: flex;
  flex-direction: column;
  gap: 16px;
  color: var(--de-text);
  font-family: var(--de-font-sans);
  font-size: 13px;
  line-height: 1.45;
}

.de-eng-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--de-border);
}

.de-eng-seg {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  background: var(--de-surface-2);
  border: 1px solid var(--de-border);
  border-radius: var(--de-radius);
}

.de-eng-seg-btn {
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--de-muted);
  background: transparent;
  border: none;
  border-radius: var(--de-radius-sm);
  cursor: pointer;
  white-space: nowrap;
  transition: background-color 140ms ease, color 140ms ease;
}

.de-eng-seg-btn:hover {
  color: var(--de-text);
}

.de-eng-seg-btn.active {
  background: var(--de-surface);
  color: var(--de-text);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.de-eng-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.de-eng-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 14px;
  font-family: var(--de-font-sans);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.2;
  white-space: nowrap;
  border-radius: var(--de-radius);
  border: 1px solid var(--de-border);
  background: var(--de-surface);
  color: var(--de-text);
  cursor: pointer;
  transition: background-color 140ms ease, border-color 140ms ease, opacity 140ms ease;
}

.de-eng-btn:hover:not(:disabled) {
  background: var(--de-surface-2);
  border-color: var(--de-border-strong);
}

.de-eng-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.de-eng-btn.primary {
  background: var(--de-accent);
  border-color: var(--de-accent);
  color: var(--de-accent-fg);
  font-weight: 600;
}

.de-eng-btn.primary:hover:not(:disabled) {
  background: var(--de-accent-hover);
  border-color: var(--de-accent-hover);
}

.de-eng-btn.danger {
  border-color: var(--de-danger);
  color: var(--de-danger);
  background: transparent;
}

.de-eng-btn.danger:hover:not(:disabled) {
  background: var(--de-danger);
  color: #ffffff;
}

.de-eng-btn.sm {
  padding: 4px 10px;
  font-size: 12px;
}

.de-eng-btn.xs {
  padding: 3px 8px;
  font-size: 11px;
}

.de-eng-workspace {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr) 268px;
  gap: 16px;
  align-items: start;
}

@media (max-width: 1160px) {
  .de-eng-workspace {
    grid-template-columns: 1fr;
  }
}

.de-eng-panel {
  background: var(--de-surface);
  border: 1px solid var(--de-border);
  border-radius: var(--de-radius-lg);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.de-eng-panel-title {
  font-family: var(--de-font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--de-text);
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.de-eng-meta {
  font-size: 12px;
  color: var(--de-muted);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.de-eng-mono {
  font-family: var(--de-font-mono);
  font-variant-numeric: tabular-nums;
}

.de-eng-input, .de-eng-select {
  width: 100%;
  box-sizing: border-box;
  padding: 7px 10px;
  font-family: var(--de-font-sans);
  font-size: 13px;
  color: var(--de-text);
  background: var(--de-bg);
  border: 1px solid var(--de-border);
  border-radius: var(--de-radius);
  outline: none;
}

.de-eng-input:focus, .de-eng-select:focus {
  border-color: var(--de-accent);
}

.de-eng-sidebar-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 520px;
  overflow-y: auto;
}

.de-eng-sidebar-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  text-align: left;
  padding: 7px 10px;
  border: none;
  border-radius: var(--de-radius-sm);
  background: transparent;
  color: var(--de-text);
  font-size: 13px;
  cursor: pointer;
}

.de-eng-sidebar-item:hover {
  background: var(--de-surface-2);
}

.de-eng-sidebar-item.active {
  background: var(--de-accent-subtle);
  color: var(--de-accent);
  font-weight: 600;
}

.de-eng-tree-scroll {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 440px;
  overflow-y: auto;
  padding-right: 4px;
}

.de-eng-cat-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  background: var(--de-surface-2);
  border-radius: var(--de-radius-sm);
  cursor: pointer;
  user-select: none;
  font-weight: 600;
  color: var(--de-text);
}

.de-eng-pkg-row {
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid var(--de-border);
  padding: 8px 6px;
  gap: 6px;
}

.de-eng-pkg-row:last-child {
  border-bottom: none;
}

.de-eng-pkg-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.de-eng-pkg-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.de-eng-expand-btn {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--de-border);
  border-radius: 4px;
  background: var(--de-bg);
  color: var(--de-muted);
  cursor: pointer;
  font-family: var(--de-font-mono);
  font-size: 11px;
  flex-shrink: 0;
}

.de-eng-pkg-name {
  font-weight: 600;
  color: var(--de-text);
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  text-align: left;
  font-size: 13px;
}

.de-eng-pkg-name:hover {
  color: var(--de-accent);
  text-decoration: underline;
}

.de-eng-units-box {
  margin-left: 28px;
  padding: 6px 0 4px 12px;
  border-top: 1px dashed var(--de-border);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.de-eng-unit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  padding: 3px 0;
}

.de-eng-check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--de-text);
}

.de-eng-status-ok { color: var(--de-success); font-weight: 600; }
.de-eng-status-warn { color: var(--de-warning); font-weight: 600; }
.de-eng-status-err { color: var(--de-danger); font-weight: 600; }
.de-eng-status-accent { color: var(--de-accent); font-weight: 600; }

.de-eng-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.62);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 900;
  padding: 20px;
}

.de-eng-modal {
  width: min(980px, 96vw);
  max-height: 90vh;
  background: var(--de-bg);
  border: 1px solid var(--de-border-strong);
  border-radius: var(--de-radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
}

.de-eng-modal-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--de-border);
  background: var(--de-surface);
}

.de-eng-modal-body {
  padding: 18px 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
}

.de-eng-modal-ftr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  border-top: 1px solid var(--de-border);
  background: var(--de-surface);
}

.de-eng-log-view {
  background: #0b1120;
  color: #e2e8f0;
  font-family: var(--de-font-mono);
  font-size: 12px;
  line-height: 1.5;
  padding: 12px 14px;
  border-radius: var(--de-radius);
  border: 1px solid var(--de-border);
  max-height: 400px;
  min-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.de-eng-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 12px;
}

.de-eng-table th {
  padding: 8px 10px;
  border-bottom: 1px solid var(--de-border);
  color: var(--de-muted);
  font-weight: 600;
  white-space: nowrap;
}

.de-eng-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--de-border);
  vertical-align: top;
}

.de-eng-table tr:hover td {
  background: var(--de-surface-2);
}

.de-eng-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: var(--de-accent-subtle);
  border: 1px solid var(--de-border);
  border-radius: var(--de-radius);
}
`;var He="de_engine_web_expanded_v3",Gt=[{value:"debian",label:"Debian (apt / systemd)"},{value:"ubuntu",label:"Ubuntu (apt / systemd)"},{value:"alpine",label:"Alpine (apk)"},{value:"arch",label:"Arch Linux (pacman)"},{value:"fedora",label:"Fedora / RHEL (dnf)"},{value:"macos",label:"macOS (brew / launchd)"}];function Xt(){try{let n=sessionStorage.getItem(He);if(n){let t=JSON.parse(n);if(Array.isArray(t))return new Set(t.map(String))}}catch{}return new Set}function Yt({sdk:n}){let[t,a]=C("orchestrator"),[s,l]=C(null),[o,p]=C(!0),[c,g]=C(!1),[b,d]=C(""),[P,h]=C("all"),[i,x]=C(()=>Xt()),[A,k]=C(null),[f,m]=C({}),[w,u]=C({}),[D,S]=C([]),[E,W]=C({}),[r,M]=C({sandbox:!1,sandbox_os:"debian",dry_run:!1,purge:!1,clean_env:!1,with_hooks:!1,comment:""}),[T,L]=C(null),[F,q]=C(null),[j,V]=C(null),[ne,Z]=C(null),[pe,ue]=C([]),[Se,v]=C(!1),$=n.can("plan.execute"),K=n.can("sandbox.run")||$,wt=n.can("repo.sync"),Ce=n.can("logs.read"),St=n.can("env.write");N(()=>{let _=n.onThemeChange(()=>{});return()=>_()},[n]);let oe=Fe(async(_,y,R=!1)=>{p(!0);try{let O=await n.api.call("get_state",{sandbox:_,sandbox_os:y});l(O),R&&x(I=>{if(I.size>0)return I;let X=new Set;for(let ae of O.packages)X.add(`cat:${ae.category||"\u043A\u043E\u0440\u0435\u043D\u044C"}`);try{sessionStorage.setItem(He,JSON.stringify(Array.from(X)))}catch{}return X})}catch(O){n.notifyToast(`\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044C \u0441\u043E\u0441\u0442\u043E\u044F\u043D\u0438\u0435 Deploy Engine: ${O.message}`,"error")}finally{p(!1)}},[n]),_e=Fe(async()=>{if(Ce){v(!0);try{let _=await n.api.call("list_jobs",{limit:50});ue(_.jobs||[])}catch(_){n.notifyToast(`\u041E\u0448\u0438\u0431\u043A\u0430 \u0437\u0430\u0433\u0440\u0443\u0437\u043A\u0438 \u0438\u0441\u0442\u043E\u0440\u0438\u0438 \u0437\u0430\u043F\u0443\u0441\u043A\u043E\u0432: ${_.message}`,"error")}finally{v(!1)}}},[n,Ce]);N(()=>{oe(r.sandbox,r.sandbox_os,!0)},[r.sandbox,r.sandbox_os]),N(()=>{t==="history"&&_e()},[t,_e]);let ge=J(()=>({actions:f,unit_updates:w,backups:D,restores:E,options:r}),[f,w,D,E,r]),G=J(()=>Object.keys(f).length>0||Object.values(w).some(_=>_.length>0)||D.length>0||Object.keys(E).length>0,[f,w,D,E]);N(()=>{if(!G){L(null);return}let _=setTimeout(()=>{n.api.call("preview_plan",{plan:ge}).then(L).catch(y=>n.notifyToast(`\u041E\u0448\u0438\u0431\u043A\u0430 \u0440\u0430\u0441\u0447\u0451\u0442\u0430 \u043F\u043B\u0430\u043D\u0430: ${y.message}`,"error"))},150);return()=>clearTimeout(_)},[ge,G,n]);let Ct=_=>{x(y=>{let R=new Set(y);R.has(_)?R.delete(_):R.add(_);try{sessionStorage.setItem(He,JSON.stringify(Array.from(R)))}catch{}return R})},Tt=(_,y)=>{m(R=>{let O={...R};return y?O[_]=y:delete O[_],O})},Pt=(_,y)=>{u(R=>{let O=new Set(R[_]||[]);O.has(y)?O.delete(y):O.add(y);let I={...R};return O.size===0?delete I[_]:I[_]=Array.from(O),I})},Et=_=>{S(y=>y.includes(_)?y.filter(R=>R!==_):[...y,_])},Dt=(_,y)=>{W(R=>{let O={...R};return y?O[_]=y:delete O[_],O})},se=()=>{m({}),u({}),S([]),W({}),L(null)},Mt=async()=>{g(!0);try{let _=await n.api.call("sync_packages",{});n.notifyToast(`\u0420\u0435\u043F\u043E\u0437\u0438\u0442\u043E\u0440\u0438\u0439 \u043E\u0431\u043D\u043E\u0432\u043B\u0451\u043D \xB7 \u043D\u0430\u0439\u0434\u0435\u043D\u043E \u043F\u0430\u043A\u0435\u0442\u043E\u0432: ${_.packages_count}`,"success"),await oe(r.sandbox,r.sandbox_os)}catch(_){n.notifyToast(`\u041E\u0448\u0438\u0431\u043A\u0430 \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u044F \u043F\u0430\u043A\u0435\u0442\u043E\u0432: ${_.message}`,"error")}finally{g(!1)}},Ue=async()=>{if(!(!r.sandbox&&!r.dry_run&&(Object.values(f).includes("uninstall")||Object.keys(E).length>0||r.purge||r.clean_env)&&!await n.requestConfirm({title:"\u041F\u043E\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u0432\u044B\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u0435 \u043F\u043B\u0430\u043D\u0430 \u043D\u0430 \u0441\u0435\u0440\u0432\u0435\u0440\u0435",message:"\u041F\u043B\u0430\u043D \u0441\u043E\u0434\u0435\u0440\u0436\u0438\u0442 \u0443\u0434\u0430\u043B\u0435\u043D\u0438\u0435 \u043F\u0430\u043A\u0435\u0442\u043E\u0432, \u0432\u043E\u0441\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435 \u0438\u0437 \u0431\u044D\u043A\u0430\u043F\u0430 \u0438\u043B\u0438 \u0441\u0431\u0440\u043E\u0441 \u0434\u0430\u043D\u043D\u044B\u0445/ENV. \u041F\u0440\u043E\u0434\u043E\u043B\u0436\u0438\u0442\u044C?",confirmText:"\u0412\u044B\u043F\u043E\u043B\u043D\u0438\u0442\u044C \u043F\u043B\u0430\u043D",danger:!0})))try{let y=await n.api.call("start_job",{plan:ge});n.notifyToast(`\u0417\u0430\u0434\u0430\u0447\u0430 ${y.job_id} \u0437\u0430\u043F\u0443\u0449\u0435\u043D\u0430`,"info"),Z(y.job_id),await oe(r.sandbox,r.sandbox_os)}catch(y){n.notifyToast(y.message||"\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u043F\u043B\u0430\u043D","error")}},Ne=async()=>{if(G){if(!r.sandbox&&!r.dry_run&&!$){n.notifyToast("\u0414\u043B\u044F \u0431\u043E\u0435\u0432\u043E\u0433\u043E \u0432\u044B\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u044F \u0442\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044F \u043F\u0440\u0430\u0432\u043E plan.execute (\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D Sandbox \u0438\u043B\u0438 Dry-Run)","warning");return}try{let _=await n.api.call("preview_plan",{plan:ge});if(L(_),_.warnings.length>0){n.notifyToast(_.warnings.join("; "),"error");return}if(_.requires_env_wizard&&!r.dry_run){let y=_.env_checks.filter(R=>R.needs_confirmation).map(R=>R.package);V(y);return}await Ue()}catch(_){n.notifyToast(`\u041E\u0448\u0438\u0431\u043A\u0430 \u043F\u043E\u0434\u0433\u043E\u0442\u043E\u0432\u043A\u0438 \u043F\u043B\u0430\u043D\u0430: ${_.message}`,"error")}}},Be=J(()=>{if(!s)return[];let _=new Set(T?.auto_dependencies||[]),y=new Map(s.packages.map(I=>[I.name,I])),R=new Set;for(let I of s.packages)(f[I.key]||(w[I.key]?.length??0)>0||D.includes(I.name)||E[I.name]||_.has(I.name))&&R.add(I.key);let O=s.packages.filter(I=>R.has(I.key)||I.installed);return O.sort((I,X)=>{let ae=R.has(I.key)?0:1,ve=R.has(X.key)?0:1;return ae!==ve?ae-ve:I.name.localeCompare(X.name,"ru")}),O.map(I=>({pkg:I,isAutoDep:_.has(I.name)&&!f[I.key],action:f[I.key]||null,units:w[I.key]||[],hasBackup:D.includes(I.name),hasRestore:!!E[I.name],refPkg:y.get(I.name)||I}))},[s,T,f,w,D,E]),Je=r.sandbox||r.dry_run?K:$;return e("div",{class:"de-eng-root",children:[e("style",{children:kt}),e("div",{class:"de-eng-topbar",children:[e("div",{style:{display:"flex",alignItems:"center",gap:"16px",flexWrap:"wrap"},children:[e("div",{class:"de-eng-seg",role:"tablist",children:[e("button",{type:"button",class:`de-eng-seg-btn ${t==="orchestrator"?"active":""}`,onClick:()=>a("orchestrator"),children:"\u041E\u0440\u043A\u0435\u0441\u0442\u0440\u0430\u0442\u043E\u0440"}),Ce&&e("button",{type:"button",class:`de-eng-seg-btn ${t==="history"?"active":""}`,onClick:()=>a("history"),children:"\u0418\u0441\u0442\u043E\u0440\u0438\u044F \u0438 \u0430\u0443\u0434\u0438\u0442"})]}),s&&e("div",{class:"de-eng-meta de-eng-mono",children:[e("span",{children:["Deploy Engine v",s.engine_version]}),e("span",{children:"\xB7"}),e("span",{children:s.sandbox?`Sandbox: ${s.sandbox_os}`:`\u0425\u043E\u0441\u0442: ${s.distro}`})]})]}),e("div",{class:"de-eng-actions",children:[wt&&e("button",{type:"button",class:"de-eng-btn",disabled:c,onClick:Mt,children:c?"\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435...":"\u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C \u043F\u0430\u043A\u0435\u0442\u044B (git pull + scan)"}),e("button",{type:"button",class:"de-eng-btn primary",disabled:!G||!Je||!!(s?.active_job_id&&!r.sandbox&&!r.dry_run),onClick:Ne,children:r.dry_run?"\u0421\u0438\u043C\u0443\u043B\u0438\u0440\u043E\u0432\u0430\u0442\u044C \u043F\u043B\u0430\u043D":r.sandbox?"\u0417\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u0432 Sandbox":"\u0412\u044B\u043F\u043E\u043B\u043D\u0438\u0442\u044C \u043F\u043B\u0430\u043D"})]})]}),s?.active_job_id&&e("div",{class:"de-eng-banner",children:[e("div",{children:[e("strong",{children:"\u0412\u044B\u043F\u043E\u043B\u043D\u044F\u0435\u0442\u0441\u044F \u0444\u043E\u043D\u043E\u0432\u0430\u044F \u0437\u0430\u0434\u0430\u0447\u0430:"})," ",e("span",{class:"de-eng-mono",children:s.active_job_id})]}),e("button",{type:"button",class:"de-eng-btn sm primary",onClick:()=>Z(s.active_job_id),children:"\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u043C\u043E\u043D\u0438\u0442\u043E\u0440 \u0438 \u043B\u043E\u0433\u0438"})]}),t==="history"?e(bt,{jobs:pe,loading:Se,onRefresh:_e,onOpenJob:_=>Z(_)}):o&&!s?e("div",{class:"de-eng-panel",style:{padding:"32px",textAlign:"center",color:"var(--de-muted)"},children:"\u0421\u043A\u0430\u043D\u0438\u0440\u043E\u0432\u0430\u043D\u0438\u0435 \u0440\u0435\u0435\u0441\u0442\u0440\u0430 \u043F\u0430\u043A\u0435\u0442\u043E\u0432 Deploy Engine..."}):s?e("div",{class:"de-eng-workspace",children:[e("div",{class:"de-eng-panel",children:[e("div",{class:"de-eng-panel-title",children:[e("span",{children:"\u041F\u0430\u043A\u0435\u0442\u044B"}),e("span",{class:"de-eng-meta de-eng-mono",children:Be.length})]}),e("div",{class:"de-eng-sidebar-list",children:[e("button",{type:"button",class:`de-eng-sidebar-item ${A===null?"active":""}`,onClick:()=>k(null),children:[e("span",{children:"\u0412\u0441\u0435 \u043F\u0430\u043A\u0435\u0442\u044B \u043F\u043B\u0430\u043D\u0430"}),e("span",{class:"de-eng-mono",style:{fontSize:"11px",color:"var(--de-muted)"},children:T?.ordered_packages.length||0})]}),Be.map(({pkg:_,isAutoDep:y,action:R,units:O,hasBackup:I,hasRestore:X})=>{let ae=R==="install"?"+":R==="reinstall"?"\u21BB":R==="uninstall"?"\u2212":y?"+ \u0434\u0435\u043F":O.length>0?`\u044E\u043D\u0438\u0442\u044B:${O.length}`:"\u2713",ve=R==="install"||y?"de-eng-status-ok":R==="reinstall"||O.length>0?"de-eng-status-warn":R==="uninstall"?"de-eng-status-err":"";return e("div",{style:{display:"flex",alignItems:"center",gap:"4px"},children:[e("button",{type:"button",class:`de-eng-sidebar-item ${A===_.name?"active":""}`,onClick:()=>k(_.name),onDblClick:()=>q({pkg:_,tab:"info"}),children:[e("span",{style:{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"},children:[_.name,I?" \xB7 \u0431\u044D\u043A\u0430\u043F":"",X?" \xB7 \u0432\u043E\u0441\u0441\u0442.":""]}),e("span",{class:`de-eng-mono ${ve}`,style:{fontSize:"11px",flexShrink:0},children:ae})]}),e("button",{type:"button",class:"de-eng-btn xs",title:"\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u043A\u0430\u0440\u0442\u043E\u0447\u043A\u0443 \u043F\u0430\u043A\u0435\u0442\u0430 \u0438 \u043B\u043E\u0433\u0438",onClick:()=>q({pkg:_,tab:"info"}),children:"\u0418\u043D\u0444\u043E"})]},_.key)})]})]}),e("div",{style:{display:"flex",flexDirection:"column",gap:"16px",minWidth:0},children:[e(xt,{packages:s.packages,categories:s.categories,search:b,onSearchChange:d,filter:P,onFilterChange:h,expandedKeys:i,onToggleExpand:Ct,actions:f,unitUpdates:w,backups:D,restores:E,onSetAction:Tt,onToggleUnit:Pt,onToggleBackup:Et,onSetRestore:Dt,onOpenDetails:(_,y="info")=>q({pkg:_,tab:y}),canWriteEnv:St}),e("div",{class:"de-eng-panel",children:[e("div",{class:"de-eng-panel-title",children:[e("span",{children:["\u041F\u0440\u0435\u0434\u043F\u0440\u043E\u0441\u043C\u043E\u0442\u0440 \u043F\u043B\u0430\u043D\u0430",A?`: ${A}`:""]}),G&&e("button",{type:"button",class:"de-eng-btn xs",onClick:se,children:"\u041E\u0447\u0438\u0441\u0442\u0438\u0442\u044C \u043F\u043B\u0430\u043D"})]}),G?T?e("div",{style:{display:"flex",flexDirection:"column",gap:"8px",fontSize:"12px"},children:[T.warnings.length>0&&e("div",{class:"de-eng-status-err",children:["\u041E\u0448\u0438\u0431\u043A\u0438 \u043F\u043B\u0430\u043D\u0430: ",T.warnings.join(" \xB7 ")]}),e("div",{children:[e("span",{style:{color:"var(--de-muted)"},children:"\u041F\u043E\u0440\u044F\u0434\u043E\u043A \u0432\u044B\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u044F: "}),e("span",{class:"de-eng-mono",style:{fontWeight:600},children:T.ordered_packages.join(" \u2192 ")||"\u2014"})]}),T.auto_dependencies.length>0&&e("div",{children:[e("span",{style:{color:"var(--de-muted)"},children:"\u041F\u043E\u0434\u0442\u044F\u043D\u0443\u0442\u044B\u0435 \u0437\u0430\u0432\u0438\u0441\u0438\u043C\u043E\u0441\u0442\u0438: "}),e("span",{class:"de-eng-mono de-eng-status-accent",children:T.auto_dependencies.join(", ")})]}),T.skipped_dependencies.length>0&&e("div",{children:[e("span",{style:{color:"var(--de-muted)"},children:"\u0423\u0436\u0435 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043B\u0435\u043D\u044B (\u043F\u0440\u043E\u043F\u0443\u0441\u043A): "}),e("span",{class:"de-eng-mono",children:T.skipped_dependencies.join(", ")})]}),T.sys_packages.length>0&&e("div",{children:[e("span",{style:{color:"var(--de-muted)"},children:["\u0421\u0438\u0441\u0442\u0435\u043C\u043D\u044B\u0435 \u043F\u0430\u043A\u0435\u0442\u044B (",T.sys_packages.length,"): "]}),e("span",{class:"de-eng-mono",children:T.sys_packages.join(", ")})]}),T.env_checks.length>0&&e("div",{children:[e("span",{style:{color:"var(--de-muted)"},children:"\u041A\u043E\u043D\u0444\u0438\u0433\u0443\u0440\u0430\u0446\u0438\u0438 .env: "}),T.env_checks.map((_,y)=>e("span",{class:"de-eng-mono",children:[y>0?" \xB7 ":"",_.package," ",e("span",{class:_.needs_confirmation?"de-eng-status-warn":"de-eng-status-ok",children:["(",_.needs_confirmation?"\u0442\u0440\u0435\u0431\u0443\u0435\u0442 \u043F\u043E\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u0438\u044F":"\u0433\u043E\u0442\u043E\u0432",")"]})]},_.package))]})]}):e("div",{style:{color:"var(--de-muted)",fontSize:"12px"},children:"\u0420\u0430\u0441\u0447\u0451\u0442 \u043F\u043E\u0440\u044F\u0434\u043A\u0430 \u0443\u0441\u0442\u0430\u043D\u043E\u0432\u043A\u0438 \u0438 \u0437\u0430\u0432\u0438\u0441\u0438\u043C\u043E\u0441\u0442\u0435\u0439..."}):e("div",{style:{color:"var(--de-muted)",fontSize:"12px"},children:"\u0412\u044B\u0431\u0435\u0440\u0438\u0442\u0435 \u043F\u0430\u043A\u0435\u0442\u044B, \u043E\u0442\u0434\u0435\u043B\u044C\u043D\u044B\u0435 \u044E\u043D\u0438\u0442\u044B \u0438\u043B\u0438 \u043E\u043F\u0435\u0440\u0430\u0446\u0438\u0438 \u0440\u0435\u0437\u0435\u0440\u0432\u043D\u043E\u0433\u043E \u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u043D\u0438\u044F \u0432 \u0434\u0435\u0440\u0435\u0432\u0435 \u0432\u044B\u0448\u0435."})]})]}),e("div",{class:"de-eng-panel",children:[e("div",{class:"de-eng-panel-title",children:"\u041F\u0430\u0440\u0430\u043C\u0435\u0442\u0440\u044B \u0437\u0430\u043F\u0443\u0441\u043A\u0430"}),e("label",{class:"de-eng-check-row",children:[e("input",{type:"checkbox",checked:r.sandbox,onChange:_=>{let y=_.target.checked;se(),M(R=>({...R,sandbox:y}))}}),e("span",{children:"Sandbox (\u043F\u0435\u0441\u043E\u0447\u043D\u0438\u0446\u0430)"})]}),r.sandbox&&e("div",{children:[e("div",{style:{fontSize:"12px",color:"var(--de-muted)",marginBottom:"4px"},children:"\u0426\u0435\u043B\u0435\u0432\u0430\u044F \u041E\u0421 \u043F\u0435\u0441\u043E\u0447\u043D\u0438\u0446\u044B"}),e("select",{class:"de-eng-select",value:r.sandbox_os,onChange:_=>{let y=_.target.value;se(),M(R=>({...R,sandbox_os:y}))},children:Gt.map(_=>e("option",{value:_.value,children:_.label},_.value))})]}),e("label",{class:"de-eng-check-row",children:[e("input",{type:"checkbox",checked:r.dry_run,onChange:_=>M(y=>({...y,dry_run:_.target.checked}))}),e("span",{children:"Dry-Run (\u0441\u0438\u043C\u0443\u043B\u044F\u0446\u0438\u044F \u0431\u0435\u0437 \u0437\u0430\u043F\u0438\u0441\u0438)"})]}),e("label",{class:"de-eng-check-row",children:[e("input",{type:"checkbox",checked:r.with_hooks,onChange:_=>M(y=>({...y,with_hooks:_.target.checked}))}),e("span",{children:"\u0412\u044B\u043F\u043E\u043B\u043D\u044F\u0442\u044C post_install \u043F\u0440\u0438 \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0438 \u044E\u043D\u0438\u0442\u043E\u0432"})]}),e("label",{class:"de-eng-check-row",children:[e("input",{type:"checkbox",checked:r.purge,onChange:_=>M(y=>({...y,purge:_.target.checked}))}),e("span",{children:"\u0423\u0434\u0430\u043B\u044F\u0442\u044C data \u0438 .env (--purge)"})]}),e("label",{class:"de-eng-check-row",children:[e("input",{type:"checkbox",checked:r.clean_env,onChange:_=>M(y=>({...y,clean_env:_.target.checked}))}),e("span",{children:"\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C .env \u043A \u0448\u0430\u0431\u043B\u043E\u043D\u0443 (--clean-env)"})]}),e("div",{children:[e("div",{style:{fontSize:"12px",color:"var(--de-muted)",marginBottom:"4px"},children:"\u041A\u043E\u043C\u043C\u0435\u043D\u0442\u0430\u0440\u0438\u0439 \u043A \u0431\u044D\u043A\u0430\u043F\u0443 / \u0437\u0430\u043F\u0443\u0441\u043A\u0443"}),e("input",{type:"text",class:"de-eng-input",placeholder:"\u041D\u0430\u043F\u0440\u0438\u043C\u0435\u0440: \u043F\u0435\u0440\u0435\u0434 \u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435\u043C \u0432\u0435\u0431-\u043C\u043E\u0434\u0443\u043B\u0435\u0439",value:r.comment,onInput:_=>M(y=>({...y,comment:_.target.value}))})]}),e("div",{class:"de-eng-meta de-eng-mono",style:{borderTop:"1px solid var(--de-border)",paddingTop:"10px"},children:e("span",{children:["\u041F\u0440\u0435\u0441\u0435\u0442\u044B: ",s.local_env_dir]})}),e("div",{style:{display:"flex",flexDirection:"column",gap:"8px"},children:[e("button",{type:"button",class:"de-eng-btn primary",style:{width:"100%"},disabled:!G||!Je,onClick:Ne,children:r.dry_run?"\u0421\u0438\u043C\u0443\u043B\u0438\u0440\u043E\u0432\u0430\u0442\u044C \u043F\u043B\u0430\u043D":r.sandbox?"\u0417\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C \u0432 Sandbox":"\u0412\u044B\u043F\u043E\u043B\u043D\u0438\u0442\u044C \u043F\u043B\u0430\u043D"}),G&&e("button",{type:"button",class:"de-eng-btn",style:{width:"100%"},onClick:se,children:"\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C \u0432\u044B\u0431\u043E\u0440"})]})]})]}):null,F&&e(ht,{sdk:n,pkg:F.pkg,initialTab:F.tab,sandbox:r.sandbox,sandboxOs:r.sandbox_os,onClose:()=>q(null),onEnvSaved:()=>oe(r.sandbox,r.sandbox_os)}),j&&e(ft,{sdk:n,pendingPackages:j,sandbox:r.sandbox,sandboxOs:r.sandbox_os,onCancel:()=>V(null),onAllConfirmed:()=>{V(null),Ue()}}),ne&&e(yt,{sdk:n,jobId:ne,onClose:()=>Z(null),onFinished:()=>{se(),oe(r.sandbox,r.sandbox_os),t==="history"&&_e()}})]})}function En(n,t){return Ie(Ye(Yt,{sdk:t}),n),()=>{Ie(null,n)}}export{En as mount};
