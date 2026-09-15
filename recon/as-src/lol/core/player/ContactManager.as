class lol.core.player.ContactManager
{
   var _contacter;
   var selectedID;
   function ContactManager()
   {
      lol.events.LEventDispatcher.initialize(this);
   }
   function selectPlayer(obj)
   {
      this.selectedID = obj.id;
      var _loc2_;
      if(this.selectedID)
      {
         _loc2_ = lol.core.Master.getInstance().getPlayer(this.selectedID);
         if(_loc2_ instanceof lol.core.player.Player)
         {
         }
      }
   }
   function set contacter(contactEntity)
   {
      this._contacter = contactEntity;
   }
   function get contacter()
   {
      return this._contacter;
   }
}
