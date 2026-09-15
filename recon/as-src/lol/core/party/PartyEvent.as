class lol.core.party.PartyEvent
{
   var body;
   var type;
   static var KICKED_FROM_PARTY = "KICKED_FROM_PARTY";
   static var LEAVE_PARTY = "LEAVE_PARTY";
   static var PARTY_LEADER_CHANGED = "PARTY_LEADER_CHANGED";
   static var JOIN_TO_PARTY = "JOIN_TO_PARTY";
   static var DISBAND_PARTY = "DISBAND_PARTY";
   static var PLAYER_RETURN_ONLINE = "RETURN_ONLINE";
   static var PLAYER_DISCONNECTED = "PLAYER_DISCONNECTED";
   static var PARTY_LIST_REFRESH = "PARTY_LIST_REFRESH";
   function PartyEvent(tType, tBody)
   {
      this.type = tType;
      this.body = tBody;
   }
}
