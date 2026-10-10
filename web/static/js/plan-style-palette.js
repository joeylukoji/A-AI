// Colors and room names are shared by the canvas and its legend.
window.PlanStylePalette = (() => {
  const fills = {
    living: '#f2f0e9',
    kitchen: '#e9eeeb',
    bedroom: '#e6d4b7',
    bathroom: '#e4eef0', wc: '#e4eef0', laundry: '#e4eef0',
    hallway: '#f2f0e9',
    garage: '#dde1df',
    office: '#e6d4b7',
    dining: '#f2f0e9',
    storage: '#ece8df',
    other: '#f1f2ee',
  };
  const labels = {
    living: 'Séjour', kitchen: 'Cuisine', bedroom: 'Chambre', bathroom: 'SDB',
    hallway: 'Couloir', garage: 'Garage', office: 'Bureau', dining: 'Salle à manger',
    storage: 'Rangement', wc: 'WC', laundry: 'Buanderie', other: 'Pièce',
  };

  function label(room) {
    const name = (room && room.name) || '';
    const type = (room && room.type) || '';
    if (name && name !== type && name !== 'other' && name !== 'Pièce') return name;
    return labels[type] || name || 'Pièce';
  }

  function fill(room) {
    return fills[(room && room.type) || 'other'] || fills.other;
  }

  return { fills, labels, label, fill };
})();
