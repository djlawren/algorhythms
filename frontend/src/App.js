
import React, { useState, useEffect } from 'react';

import PlaylistList from './Components/PlaylistList';
import RecommendationGraph from './Components/RecommendationGraph';
import SpotifyInterface from './Components/SpotifyInterface';
import AlgoRhythmsInterface from './Components/AlgoRhythmsInterface';

import SpotifyPlayer from 'react-spotify-web-playback';
import Container from 'react-bootstrap/Container';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';

import './App.css';
import 'bootstrap/dist/css/bootstrap.css';


function App() {
  const [playlists, setPlaylists] = useState([]);
  const [activePlaylist, setActivePlaylist] = useState("");
  const [tracks, setTracks] = useState([]);
  const [recommendations, setRecommendations] = useState({
    source_nodes: [],
    recommendation_nodes: [],
    edges: []
  });
  const [spotifyToken, setSpotifyToken] = useState("");
  const [playbackSong, setPlaybackSong] = useState("");

  return (
    <div className="App" style={{height: '100vh'}}>
      <div className='App-header'>AlgoRhythms</div>
      <Container fluid style={{display: 'block', width: '90%'}}>
        <Row>
          <Col>
            <Row>
              <SpotifyInterface 
                setPlaylists={setPlaylists}
                activePlaylist={activePlaylist}
                setTracks={setTracks}
                setSpotifyToken={setSpotifyToken}
              />
            </Row>
            <Row>
              <PlaylistList 
                playlists={playlists}
                setActivePlaylist={setActivePlaylist}
              />
            </Row>
          </Col>
          <Col xs={8}>
            <RecommendationGraph
              recommendations={recommendations}
              setPlaybackSong={setPlaybackSong}
            />
            <AlgoRhythmsInterface
              playlistTracks={tracks}
              setRecommendations={setRecommendations}
            />
          </Col>
        </Row>
        <Row style={{paddingTop: '40px'}}>
          <Col style={{justifyContent: 'center'}}>
            <SpotifyPlayer
              token={spotifyToken}
              uris={[playbackSong]}
            />
          </Col>
        </Row>
      </Container>
    </div>
  );
}

export default App;
