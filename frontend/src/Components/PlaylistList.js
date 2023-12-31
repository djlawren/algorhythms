import ListGroup from 'react-bootstrap/ListGroup';

const PlaylistList = ({ playlists, setActivePlaylist }) => {
    const items = () => {
        if (playlists == null) return [];

        return playlists.map(playlist => {
            return (
                <ListGroup.Item action onClick={() => setActivePlaylist(playlist.id)} key={playlist.id}>
                    {playlist.name}
                </ListGroup.Item>
            )
        });
    }

    return (
        <div style={{height: '100%', marginTop: '30px', paddingRight: '30px', paddingLeft: '30px', overflowY: 'scroll'}}>
            <ListGroup variant='flush'>
                {items()}
            </ListGroup>
        </div>
    );
};

export default PlaylistList;