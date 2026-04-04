
import { Route, Routes } from 'react-router-dom';
import Onboarding from './Onboarding';

const App = () => {
  return (
  <Routes>
        <Route path='/' element={<Onboarding/>}/>
  </Routes>
    
  ) 
}

export default App