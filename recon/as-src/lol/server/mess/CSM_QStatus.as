class lol.server.mess.CSM_QStatus extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_QStatus(q_type)
   {
      super();
      this._name = "q_status";
      this.addProp("q_type",q_type);
   }
}
