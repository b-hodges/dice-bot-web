function abortRequest(request) {
    if (request !== undefined) {
        request.abort()
    }
}

function Container(props) {
    const className = (props.className) ? "container " + props.className : "container"
    return <div {...props} className={className}>{props.children}</div>
}

function Error(props) {
    return <p className="alert alert-danger">{props.children}</p>
}

function Warning(props) {
    return <p className="alert alert-warning">{props.children}</p>
}

function Paragraphs(props) {
    if (!props.children) {
        return null
    }
    else {
        let className = 'paragraphs border rounded p-3'
        className = (props.className) ? props.className + ' ' + className : className
        return (
            <div {...props} className={className}>
                {props.children}
            </div>
        )
    }
}

let remarkableOptions = {linkify: true}
let remarkableSubset = {
    core: ['block', 'inline', 'linkify'],
    block: ['fences', 'paragraph'],
    inline: ['backticks', 'del', 'emphasis', 'escape', 'text']
}

function discordRemarkable() {
    const md = new Remarkable('default', remarkableOptions)
    Object.entries(remarkableSubset).forEach((item) => md[item[0]].ruler.enable(item[1], true))
    var link_open = md.renderer.rules.link_open
    // open links in new windows
    md.renderer.rules.link_open = function() {
        const link = link_open.apply(this, arguments)
        const pos = link.length - 1
        return link.substring(0, pos) + ' target="_blank"' + link.substring(pos)
    }
    return md
}

class RevealText extends React.Component {
    constructor(props) {
        super(props)
        this.toggle = this.toggle.bind(this)
        this.state = {open: false}
    }

    toggle() {
        this.setState((prevState, props) => ({open: !prevState.open}))
    }

    render() {
        let className = 'paragraphs border rounded p-3'
        if (this.state.open) {
            className += ' tallbox'
        }
        else {
            className += ' shortbox'
        }
        className = (this.props.className) ? this.props.className + ' ' + className : className
        return (
            <div {...this.props} className={className} onClick={this.toggle}>
                {this.props.children}
            </div>
        )
    }
}

function Markdown(props) {
    const md = discordRemarkable()
    return (
        <div {...props} content={undefined} dangerouslySetInnerHTML={{__html: md.render(props.content).trim()}} />
    )
}

function User(props) {
    const size = props.iconSize || 32
    let avatar
    let name
    if (props.user !== 'DM') {
        if (props.user.avatar) {
            avatar = 'https://cdn.discordapp.com/avatars/' + props.user.id + '/' + props.user.avatar + '.png?size=' + size
        }
        else {
            avatar = 'https://cdn.discordapp.com/embed/avatars/' + props.user.discriminator % 5 + '.png?size=' + size
        }
        name = (props.user.nick) ? props.user.nick + ' (' + props.user.username + ')' : props.user.username
    }
    else {
        avatar = '/static/images/favicon.ico'
        name = 'DM'
    }
    let body = (
        <span>
            {(props.hidePrefix) ? null : "User: "}<img className={"img-thumbnail icon-" + size} src={avatar} alt={name + " icon"} /> {name}
        </span>
    )
    if (props.href) {
        body = <a href={props.href}>{body}</a>
    }
    if (!props.inline) {
        body = <p>{body}</p>
    }
    return body
}

function Server(props) {
    const size = props.iconSize || 32
    const icon = (props.server.icon)
        ? 'https://cdn.discordapp.com/icons/' + props.server.id + '/' + props.server.icon + '.png?size=' + size
        : 'https://cdn.discordapp.com/embed/avatars/0.png?size=' + size
    let body = (
        <span>
            {(props.hidePrefix) ? null : "Server: "}<img className={"img-thumbnail icon-" + size} src={icon} alt={props.server.name + " icon"} /> {props.server.name}
        </span>
    )
    if (props.href) {
        body = <a href={props.href}>{body}</a>
    }
    if (!props.inline) {
        body = <p>{body}</p>
    }
    return body
}

class LoadingButton extends React.Component {
    constructor(props) {
        super(props)
        this.error = this.error.bind(this)
        this.onClick = this.onClick.bind(this)
        this.state = {loading: false}
    }

    error(message, jqXHR) {
        this.setState({loading: false})
        this.props.onError(message, jqXHR)
    }

    onClick(e) {
        const callback = (data) => {
            this.setState({loading: false})
            this.props.callback(data)
        }
        this.setState({loading: true})
        console.log(this.props.data)
        this.request = $.ajax({
            url: this.props.url,
            type: this.props.method,
            dataType: 'json',
            data: this.props.data,
            error: (jqXHR) => this.error("Failed request", jqXHR),
            success: this.props.callback,
        })
    }

    componentWillUnmount() {
        if (this.request !== undefined) {
            this.request.abort()
        }
    }

    render() {
        if (!this.state.loading) {
            return <button {...this.props} callback="" onClick={this.onClick}>{this.props.children}</button>
        }
        else {
            return <button {...this.props} callback=""><span className="loading-animation" dot="&bull;">&bull;</span></button>
        }
    }
}

class ErrorHandler extends React.Component {
    constructor(props) {
        super(props)
        this.error = this.error.bind(this)
        this.reload = this.reload.bind(this)
        this.state = {error: []}
    }

    error(message, jqXHR) {
        if (jqXHR !== undefined) {
            const status = jqXHR.status
            if (status == 400) {
                message += " Bad request"
            }
            else if (status == 401) {
                message += " You must be logged in to access this resource (you may need to log out and log back in)"
            }
            else if (status == 403) {
                message += " You do not have access to edit this character"
            }
            else if (status == 404) {
                message += " Could not be found"
            }
            else if (status == 409) {
                message += " Conflicted with another value"
            }
            else if (status == 500) {
                message += " Server error"
            }
        }
        this.setState((prevState, props) => ({error: [message].concat(prevState.error)}))
    }

    reload(e) {
        this.setState({error: []})
    }

    componentDidCatch(error, info) {
        this.error("Unknown error")
    }

    render() {
        if (this.state.error.length === 0) {
            return React.Children.map(this.props.children, (item) => React.cloneElement(item, {onError: this.error}))
        }
        else {
            return (
                <Container>
                    {this.state.error.map((item) => <Error key={item}>{item}</Error>)}
                    <button className="btn btn-info btn-block" onClick={this.reload}>Reload</button>
                </Container>
            )
        }
    }
}

const urlparams = new URLSearchParams(window.location.search)
